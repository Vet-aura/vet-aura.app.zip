"""Voice overage → Stripe metered usage records.

Design:
  - Vetaura's Stripe catalog defines a metered price `vetaura_voice_overage_metered` at
    $0.35/min. Overage is billed on Vetaura's side (that's Vetaura revenue), NOT on the
    clinic's Twilio bill (which is separate — clinic pays Twilio directly per their own
    account).
  - At the start of every subscription (or when a clinic first goes over cap), we attach
    the metered price as an ADDITIONAL subscription item. This is idempotent.
  - A cron endpoint (auth: internal token) sweeps all clinics on the last day of the
    billing cycle and reports the overage minutes to Stripe via SubscriptionItem usage.
    On next invoice Stripe adds the overage to the clinic's bill.
  - An admin `preview` endpoint returns the current overage tally without recording it.
"""
from __future__ import annotations
import os
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional
from fastapi import APIRouter, HTTPException, Header, Depends
import stripe
from motor.motor_asyncio import AsyncIOMotorDatabase

logger = logging.getLogger(__name__)


VOICE_PLAN_CAPS = {
    "starter": 0,
    "growth": 200,
    "pro": 800,
    "solo": 50,
    "clinic": 250,
    "multi-site": 1000,
    "demo": 30,
}


async def _month_bounds(now: datetime) -> tuple[str, str]:
    start = datetime(now.year, now.month, 1, tzinfo=timezone.utc)
    if now.month == 12:
        end = datetime(now.year + 1, 1, 1, tzinfo=timezone.utc)
    else:
        end = datetime(now.year, now.month + 1, 1, tzinfo=timezone.utc)
    return start.isoformat(), end.isoformat()


async def compute_overage_minutes(db: AsyncIOMotorDatabase, clinic_id: str, plan: str,
                                  since_iso: str, until_iso: str) -> tuple[int, int]:
    """Return (voice_minutes, overage_minutes) in the [since, until) window."""
    rows = await db.voice_usage.aggregate([
        {"$match": {"clinic_id": clinic_id, "kind": "voice",
                    "at": {"$gte": since_iso, "$lt": until_iso}}},
        {"$group": {"_id": None, "seconds": {"$sum": "$seconds"}}},
    ]).to_list(1)
    voice_seconds = rows[0]["seconds"] if rows else 0
    voice_min = int(voice_seconds // 60)  # floor to whole minutes for billing fairness
    cap = VOICE_PLAN_CAPS.get((plan or "starter").lower(), 0)
    return voice_min, max(0, voice_min - cap)


async def _ensure_metered_price() -> str:
    """Idempotently create the metered $0.35/min overage price. Returns its Stripe price id."""
    # Try lookup key first
    existing = stripe.Price.list(lookup_keys=["vetaura_voice_overage_metered"], active=True, limit=1).data
    if existing:
        return existing[0].id
    # Find/create the product
    product = None
    for p in stripe.Product.list(active=True, limit=100).auto_paging_iter():
        if p.to_dict().get("metadata", {}).get("emergent_product_id") == "vetaura_voice_overage":
            product = p
            break
    if not product:
        product = stripe.Product.create(
            name="Vetaura Voice Overage",
            description="Metered voice-minute overage above your plan allowance.",
            unit_label="minute",
            metadata={"managed_by": "emergent", "emergent_product_id": "vetaura_voice_overage"},
        )
    price = stripe.Price.create(
        product=product.id,
        currency="usd",
        unit_amount=35,       # $0.35
        recurring={"interval": "month", "usage_type": "metered", "aggregate_usage": "sum"},
        lookup_key="vetaura_voice_overage_metered",
        transfer_lookup_key=True,
        billing_scheme="per_unit",
    )
    logger.info("Created metered voice overage price")
    return price.id


async def _ensure_metered_subitem(subscription_id: str, metered_price_id: str) -> str:
    """Attach the metered price to the subscription if not already present. Return the subitem id."""
    sub = stripe.Subscription.retrieve(subscription_id, expand=["items.data.price"])
    for item in sub["items"]["data"]:
        if item["price"]["id"] == metered_price_id:
            return item["id"]
    item = stripe.SubscriptionItem.create(subscription=subscription_id, price=metered_price_id)
    return item["id"]


async def record_overage_for_clinic(db: AsyncIOMotorDatabase, clinic: dict, dry_run: bool = False) -> dict:
    cid = clinic["clinic_id"]
    plan = (clinic.get("plan") or "starter").lower()
    sub_id = clinic.get("stripe_subscription_id")
    if not sub_id:
        return {"clinic_id": cid, "skipped": "no_active_subscription"}
    now = datetime.now(timezone.utc)
    since, until = await _month_bounds(now)
    voice_min, overage_min = await compute_overage_minutes(db, cid, plan, since, until)
    if overage_min <= 0:
        return {"clinic_id": cid, "voice_minutes": voice_min, "overage_minutes": 0, "action": "no_overage"}
    if dry_run:
        return {"clinic_id": cid, "voice_minutes": voice_min, "overage_minutes": overage_min, "action": "would_bill"}
    # Ensure metered price + subitem
    metered_price_id = await _ensure_metered_price()
    subitem_id = await _ensure_metered_subitem(sub_id, metered_price_id)
    # Idempotency: one usage record per clinic per billing month (fresh timestamp each call
    # would double-bill). We track in DB.
    period_key = now.strftime("%Y-%m")
    existing = await db.overage_records.find_one({"clinic_id": cid, "period": period_key})
    if existing:
        # increment the delta (append the new overage that's above what we already reported)
        prev = int(existing.get("overage_minutes_reported", 0))
        delta = max(0, overage_min - prev)
        if delta == 0:
            return {"clinic_id": cid, "voice_minutes": voice_min, "overage_minutes": overage_min, "action": "already_reported"}
        stripe.SubscriptionItem.create_usage_record(
            subscription_item=subitem_id,
            quantity=delta,
            timestamp=int(now.timestamp()),
            action="increment",
        )
        await db.overage_records.update_one(
            {"_id": existing["_id"]},
            {"$set": {"overage_minutes_reported": overage_min,
                      "last_reported_at": now.isoformat()}},
        )
        return {"clinic_id": cid, "voice_minutes": voice_min, "overage_minutes": overage_min, "delta_reported": delta, "action": "increment"}
    # First report this period
    stripe.SubscriptionItem.create_usage_record(
        subscription_item=subitem_id,
        quantity=overage_min,
        timestamp=int(now.timestamp()),
        action="increment",
    )
    await db.overage_records.insert_one({
        "clinic_id": cid,
        "period": period_key,
        "subitem_id": subitem_id,
        "overage_minutes_reported": overage_min,
        "voice_minutes": voice_min,
        "first_reported_at": now.isoformat(),
        "last_reported_at": now.isoformat(),
    })
    return {"clinic_id": cid, "voice_minutes": voice_min, "overage_minutes": overage_min, "delta_reported": overage_min, "action": "first_report"}


def build_billing_cycle_routes(db: AsyncIOMotorDatabase, auth_dep):
    router = APIRouter(prefix="/api/billing-cycle")

    @router.get("/preview")
    async def preview(user=Depends(auth_dep)):
        """Show the calling clinic's own current overage tally (no Stripe write)."""
        clinic = await db.clinics.find_one({"clinic_id": user["clinic_id"]}, {"_id": 0})
        if not clinic:
            raise HTTPException(404, "Clinic not found")
        return await record_overage_for_clinic(db, clinic, dry_run=True)

    @router.post("/close")
    async def close_cycle(x_admin_token: Optional[str] = Header(None)):
        """Admin cron endpoint — sweeps ALL clinics.

        Requires header X-Admin-Token matching env VETAURA_ADMIN_TOKEN.
        Intended to be triggered by an external scheduler once at end of each billing month.
        """
        admin = os.environ.get("VETAURA_ADMIN_TOKEN", "")
        if not admin or x_admin_token != admin:
            raise HTTPException(403, "Admin token required")
        results = []
        async for clinic in db.clinics.find({"plan_status": {"$in": ["active", "trial"]}}, {"_id": 0}):
            try:
                r = await record_overage_for_clinic(db, clinic, dry_run=False)
                results.append(r)
            except Exception as e:
                logger.exception(f"Overage billing failed for {clinic.get('clinic_id')}: {e}")
                results.append({"clinic_id": clinic.get("clinic_id"), "error": str(e)})
        return {"reported": results, "count": len(results)}

    return router
