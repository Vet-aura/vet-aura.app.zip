"""Stripe subscription setup + checkout + webhook for Vetaura."""
import os
import stripe
import logging
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Request, Depends
from pydantic import BaseModel
from motor.motor_asyncio import AsyncIOMotorDatabase

logger = logging.getLogger(__name__)

stripe.api_key = os.environ.get("STRIPE_SECRET_KEY") or "sk_test_emergent"
STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET", "")

# Determine SMP eligibility (US -> yes; SaaS is digital)
SMP_COUNTRIES = {"AU","AT","BE","BG","CA","HR","CY","CZ","DK","EE","FI","FR","DE","GI","GR","HK","HU","IE","IT","JP","LV","LI","LT","LU","MT","NL","NO","PL","PT","RO","SG","SK","SI","ES","SE","CH","GB","US"}


CATALOG = [
    {
        "emergent_product_id": "vetaura_solo",
        "name": "Vetaura Solo",
        "description": "For solo vets and mobile practices.",
        "tax_code": "txcd_10103001",
        "prices": [
            {"lookup_key": "vetaura_solo_monthly", "amount": 4900, "currency": "usd", "interval": "month", "trial_period_days": 14},
        ],
    },
    {
        "emergent_product_id": "vetaura_clinic",
        "name": "Vetaura Clinic",
        "description": "For small-to-medium clinics with up to 8 staff.",
        "tax_code": "txcd_10103001",
        "prices": [
            {"lookup_key": "vetaura_clinic_monthly", "amount": 19900, "currency": "usd", "interval": "month", "trial_period_days": 14},
        ],
    },
    {
        "emergent_product_id": "vetaura_multisite",
        "name": "Vetaura Multi-site",
        "description": "For hospital groups and multi-location practices.",
        "tax_code": "txcd_10103001",
        "prices": [
            {"lookup_key": "vetaura_multisite_monthly", "amount": 49900, "currency": "usd", "interval": "month", "trial_period_days": 14},
        ],
    },
]


def ensure_catalog():
    """Idempotently create Vetaura products + prices."""
    try:
        for entry in CATALOG:
            # find product by metadata
            product = None
            for p in stripe.Product.list(active=True, limit=100).auto_paging_iter():
                if p.to_dict().get("metadata", {}).get("emergent_product_id") == entry["emergent_product_id"]:
                    product = p
                    break
            if not product:
                product = stripe.Product.create(
                    name=entry["name"],
                    description=entry["description"],
                    tax_code=entry.get("tax_code"),
                    metadata={"managed_by": "emergent", "emergent_product_id": entry["emergent_product_id"]},
                )
                logger.info(f"Stripe product created: {entry['name']}")
            for price in entry["prices"]:
                existing = stripe.Price.list(lookup_keys=[price["lookup_key"]], active=True, limit=1).data
                if existing and (existing[0].unit_amount != price["amount"] or existing[0].currency != price["currency"]):
                    stripe.Price.modify(existing[0].id, active=False)
                    existing = []
                if not existing:
                    kwargs = dict(
                        product=product.id,
                        unit_amount=price["amount"],
                        currency=price["currency"],
                        lookup_key=price["lookup_key"],
                        transfer_lookup_key=True,
                    )
                    if price.get("interval"):
                        kwargs["recurring"] = {"interval": price["interval"]}
                    stripe.Price.create(**kwargs)
                    logger.info(f"Stripe price created: {price['lookup_key']}")
    except Exception as e:
        logger.warning(f"ensure_catalog: {e}")


def get_tax_mode() -> str:
    try:
        acc = stripe.Account.retrieve()
        return "full" if acc.country in SMP_COUNTRIES else "calc_only"
    except Exception:
        return "calc_only"


# ---------- Routes ----------
stripe_router = APIRouter(prefix="/api")


class CheckoutReq(BaseModel):
    lookup_key: str
    origin_url: str


def build_stripe_routes(db: AsyncIOMotorDatabase, auth_dep):
    @stripe_router.get("/plans")
    async def list_plans():
        """Public: return plan catalog with Stripe prices for the marketing site."""
        out = []
        for entry in CATALOG:
            for pr in entry["prices"]:
                existing = stripe.Price.list(lookup_keys=[pr["lookup_key"]], active=True, limit=1).data
                if existing:
                    out.append({
                        "product": entry["name"],
                        "description": entry["description"],
                        "lookup_key": pr["lookup_key"],
                        "amount": pr["amount"],
                        "currency": pr["currency"],
                        "interval": pr.get("interval"),
                        "trial_period_days": pr.get("trial_period_days"),
                    })
        return {"plans": out}

    @stripe_router.post("/payments/checkout")
    async def checkout(req: CheckoutReq, user=Depends(auth_dep)):
        prices = stripe.Price.list(lookup_keys=[req.lookup_key], active=True, limit=1).data
        if not prices:
            raise HTTPException(400, f"Plan not found: {req.lookup_key}")
        price = prices[0]

        # Ensure Stripe customer for the clinic
        clinic = await db.clinics.find_one({"clinic_id": user["clinic_id"]}, {"_id": 0})
        customer_id = clinic.get("stripe_customer_id")
        if not customer_id:
            cust = stripe.Customer.create(
                email=user["email"],
                name=clinic["name"],
                metadata={"clinic_id": clinic["clinic_id"]},
            )
            customer_id = cust.id
            await db.clinics.update_one({"clinic_id": user["clinic_id"]}, {"$set": {"stripe_customer_id": customer_id}})

        # 14-day trial via subscription_data
        trial_days = 14
        # find trial from catalog
        for c in CATALOG:
            for pr in c["prices"]:
                if pr["lookup_key"] == req.lookup_key and pr.get("trial_period_days"):
                    trial_days = pr["trial_period_days"]

        kwargs = dict(
            customer=customer_id,
            line_items=[{"price": price.id, "quantity": 1}],
            mode="subscription",
            success_url=f"{req.origin_url}/payment/success?session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=f"{req.origin_url}/app/billing",
            metadata={"clinic_id": clinic["clinic_id"], "lookup_key": req.lookup_key},
            subscription_data={"trial_period_days": trial_days, "metadata": {"clinic_id": clinic["clinic_id"]}},
        )

        tax_mode = get_tax_mode()
        try:
            if tax_mode == "full":
                try:
                    session = stripe.checkout.Session.create(**kwargs, managed_payments={"enabled": True})
                except stripe.error.InvalidRequestError as e:
                    msg = (e.user_message or "").lower()
                    if "managed payments" in msg or "ineligible" in msg:
                        session = stripe.checkout.Session.create(**kwargs, automatic_tax={"enabled": True}, billing_address_collection="required")
                    else:
                        raise
            else:
                session = stripe.checkout.Session.create(**kwargs, automatic_tax={"enabled": True}, billing_address_collection="required")
        except stripe.error.StripeError as e:
            logger.error(f"Stripe checkout error: {e}")
            raise HTTPException(500, "Stripe checkout error")

        await db.payment_transactions.insert_one({
            "session_id": session.id,
            "clinic_id": clinic["clinic_id"],
            "lookup_key": req.lookup_key,
            "amount": price.unit_amount,
            "currency": price.currency,
            "status": "initiated",
            "payment_status": "pending",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        })
        return {"checkout_url": session.url, "session_id": session.id}

    @stripe_router.get("/payments/status/{session_id}")
    async def status(session_id: str):
        record = await db.payment_transactions.find_one({"session_id": session_id}, {"_id": 0})
        if not record:
            raise HTTPException(404, "Transaction not found")
        if record.get("payment_status") != "paid":
            try:
                s = stripe.checkout.Session.retrieve(session_id)
                if s.payment_status == "paid" or s.status == "complete":
                    await db.payment_transactions.update_one(
                        {"session_id": session_id, "payment_status": {"$ne": "paid"}},
                        {"$set": {"status": "completed", "payment_status": "paid",
                                  "stripe_subscription_id": s.subscription,
                                  "stripe_payment_intent_id": s.payment_intent,
                                  "updated_at": datetime.now(timezone.utc).isoformat()}},
                    )
                    # Also mark clinic subscription active
                    if record.get("clinic_id"):
                        plan = record.get("lookup_key", "").replace("vetaura_", "").split("_")[0]
                        await db.clinics.update_one({"clinic_id": record["clinic_id"]}, {"$set": {
                            "plan": plan or "solo",
                            "plan_status": "active",
                            "stripe_subscription_id": s.subscription,
                        }})
                    record = await db.payment_transactions.find_one({"session_id": session_id}, {"_id": 0})
            except stripe.error.StripeError:
                pass
        return {"session_id": record["session_id"], "status": record["status"], "payment_status": record["payment_status"]}

    @stripe_router.post("/payments/portal")
    async def billing_portal(req: dict, user=Depends(auth_dep)):
        clinic = await db.clinics.find_one({"clinic_id": user["clinic_id"]}, {"_id": 0})
        if not clinic.get("stripe_customer_id"):
            raise HTTPException(400, "No billing account yet")
        origin_url = req.get("origin_url", "")
        try:
            portal = stripe.billing_portal.Session.create(
                customer=clinic["stripe_customer_id"],
                return_url=f"{origin_url}/app/billing",
            )
            return {"portal_url": portal.url}
        except stripe.error.StripeError as e:
            raise HTTPException(500, str(e))

    @stripe_router.post("/stripe/webhook")
    async def webhook(request: Request):
        payload = await request.body()
        sig = request.headers.get("stripe-signature", "")
        try:
            event = stripe.Webhook.construct_event(payload, sig, STRIPE_WEBHOOK_SECRET)
        except Exception:
            raise HTTPException(400, "Invalid signature")

        obj, t = event["data"]["object"], event["type"]
        if t == "checkout.session.completed":
            await db.payment_transactions.update_one(
                {"session_id": obj["id"], "payment_status": {"$ne": "paid"}},
                {"$set": {"status": "completed", "payment_status": obj.get("payment_status", "paid"),
                          "stripe_subscription_id": obj.get("subscription"),
                          "stripe_payment_intent_id": obj.get("payment_intent"),
                          "updated_at": datetime.now(timezone.utc).isoformat()}},
            )
            clinic_id = (obj.get("metadata") or {}).get("clinic_id")
            lookup = (obj.get("metadata") or {}).get("lookup_key", "")
            if clinic_id:
                plan = lookup.replace("vetaura_", "").split("_")[0] or "solo"
                await db.clinics.update_one({"clinic_id": clinic_id}, {"$set": {
                    "plan": plan,
                    "plan_status": "active",
                    "stripe_subscription_id": obj.get("subscription"),
                }})
        elif t in ("customer.subscription.deleted", "customer.subscription.paused"):
            sub_id = obj.get("id")
            await db.clinics.update_one({"stripe_subscription_id": sub_id}, {"$set": {"plan_status": "canceled"}})
        elif t == "customer.subscription.updated":
            sub_id = obj.get("id")
            status_v = obj.get("status")
            await db.clinics.update_one({"stripe_subscription_id": sub_id}, {"$set": {"plan_status": status_v}})
        return {"status": "ok"}

    return stripe_router
