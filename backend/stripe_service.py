"""Stripe subscription setup + checkout + webhook for Vetaura."""
import os
import stripe
import logging
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, HTTPException, Request, Depends
from pydantic import BaseModel
from motor.motor_asyncio import AsyncIOMotorDatabase

logger = logging.getLogger(__name__)

stripe.api_key = os.environ["STRIPE_SECRET_KEY"]
STRIPE_WEBHOOK_SECRET = os.environ["STRIPE_WEBHOOK_SECRET"]

# Determine SMP eligibility (US -> yes; SaaS is digital)
SMP_COUNTRIES = {"AU","AT","BE","BG","CA","HR","CY","CZ","DK","EE","FI","FR","DE","GI","GR","HK","HU","IE","IT","JP","LV","LI","LT","LU","MT","NL","NO","PL","PT","RO","SG","SK","SI","ES","SE","CH","GB","US"}


CATALOG = [
    {
        "emergent_product_id": "vetaura_starter",
        "name": "Vetaura Starter",
        "description": "For solo or small clinics — Inbox copilot & Receptionist chat.",
        "tax_code": "txcd_10103001",
        "prices": [
            {"lookup_key": "vetaura_starter_monthly", "amount": 24900, "currency": "usd", "interval": "month", "trial_period_days": 14},
        ],
    },
    {
        "emergent_product_id": "vetaura_growth",
        "name": "Vetaura Growth",
        "description": "For the typical 2–5 doctor clinic — adds Ambient Scribe & 200 voice minutes.",
        "tax_code": "txcd_10103001",
        "prices": [
            {"lookup_key": "vetaura_growth_monthly", "amount": 49900, "currency": "usd", "interval": "month", "trial_period_days": 14},
        ],
    },
    {
        "emergent_product_id": "vetaura_pro",
        "name": "Vetaura Pro",
        "description": "For busy clinics — Phone/SMS routing, 800 voice minutes, priority support.",
        "tax_code": "txcd_10103001",
        "prices": [
            {"lookup_key": "vetaura_pro_monthly", "amount": 89900, "currency": "usd", "interval": "month", "trial_period_days": 14},
        ],
    },
    {
        "emergent_product_id": "vetaura_scribe_addon",
        "name": "Vetaura Scribe (per DVM add-on)",
        "description": "Ambient SOAP scribe — per veterinarian.",
        "tax_code": "txcd_10103001",
        "prices": [
            {"lookup_key": "vetaura_scribe_addon_monthly", "amount": 7900, "currency": "usd", "interval": "month", "trial_period_days": 14},
        ],
    },
]

BUNDLE_COUPON_ID = "vetaura_scribe_bundle_20"
BUNDLE_COUPON_NAME = "Scribe bundle · 20% off"
BUNDLE_COUPON_PERCENT_OFF = 20.0


def ensure_catalog():
    """Idempotently create Vetaura products + prices + bundle coupon."""
    try:
        # products & prices
        product_by_lookup: dict[str, str] = {}
        for entry in CATALOG:
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
                product_by_lookup[price["lookup_key"]] = product.id

        # Bundle coupon (applies only to the Scribe add-on product)
        scribe_product_id = product_by_lookup.get("vetaura_scribe_addon_monthly")
        if scribe_product_id:
            try:
                stripe.Coupon.retrieve(BUNDLE_COUPON_ID)
            except stripe.error.InvalidRequestError:
                stripe.Coupon.create(
                    id=BUNDLE_COUPON_ID,
                    name=BUNDLE_COUPON_NAME,
                    percent_off=BUNDLE_COUPON_PERCENT_OFF,
                    duration="forever",
                    applies_to={"products": [scribe_product_id]},
                    metadata={"managed_by": "emergent"},
                )
                logger.info("Stripe bundle coupon created")
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


class BundleCheckoutReq(BaseModel):
    core_lookup_key: str
    origin_url: str
    attach_scribe: bool = False
    scribe_quantity: int = 1


def safe_origin(origin: str, request: Request) -> str:
    """Only redirect Stripe back to our own app (same host as this API, PUBLIC_APP_URL or CORS list)."""
    base = os.environ["PUBLIC_APP_URL"].rstrip("/")
    allowed = {o.strip().rstrip("/") for o in os.environ.get("CORS_ORIGINS", "").split(",") if o.strip() not in ("", "*")}
    allowed.add(base)
    host = request.headers.get("x-forwarded-host") or request.headers.get("host")
    if host:
        allowed.add(f"https://{host}")
        base = f"https://{host}"
    o = (origin or "").rstrip("/")
    return o if o in allowed else base


def _iso(ts) -> str:
    return datetime.fromtimestamp(int(ts), tz=timezone.utc).isoformat()


def _sub_id_from_invoice(inv: dict):
    return inv.get("subscription") or (((inv.get("parent") or {}).get("subscription_details") or {}).get("subscription"))


def build_stripe_routes(db: AsyncIOMotorDatabase, auth_dep):
    async def sync_subscription(sub: dict, clinic_id: str = None, plan: str = None):
        """Mirror a Stripe Subscription onto the clinic doc (status, trial end, renewal, past-due clock)."""
        sub = sub.to_dict() if hasattr(sub, "to_dict") else sub
        clinic_id = clinic_id or (sub.get("metadata") or {}).get("clinic_id")
        q = {"clinic_id": clinic_id} if clinic_id else {"stripe_subscription_id": sub["id"]}
        items = ((sub.get("items") or {}).get("data") or [{}])
        period_end = sub.get("current_period_end") or items[0].get("current_period_end")
        upd = {"plan_status": sub["status"], "stripe_subscription_id": sub["id"],
               "cancel_at_period_end": bool(sub.get("cancel_at_period_end")),
               "current_period_end": _iso(period_end) if period_end else None,
               "billing_synced_at": datetime.now(timezone.utc).isoformat()}
        if sub.get("customer"):
            upd["stripe_customer_id"] = sub["customer"]
        if sub.get("trial_end"):
            upd["trial_ends_at"] = _iso(sub["trial_end"])
        if plan:
            upd["plan"] = plan
        await db.clinics.update_one(q, {"$set": upd})
        if sub["status"] == "past_due":
            await db.clinics.update_one({**q, "past_due_since": {"$exists": False}},
                                        {"$set": {"past_due_since": datetime.now(timezone.utc).isoformat()}})
        else:
            await db.clinics.update_one(q, {"$unset": {"past_due_since": "", "billing_notice": ""}} if sub["status"] == "active"
                                        else {"$unset": {"past_due_since": ""}})

    async def prepare_checkout(user: dict) -> tuple[dict, str, int]:
        """Owner-only; blocks double subscriptions; carries over remaining in-app trial days."""
        if user.get("role", "owner") != "owner":
            raise HTTPException(403, "Only clinic owners can manage the subscription.")
        clinic = await db.clinics.find_one({"clinic_id": user["clinic_id"]}, {"_id": 0})
        if clinic.get("stripe_subscription_id") and clinic.get("plan_status") in ("active", "trialing", "past_due"):
            raise HTTPException(400, "You already have a subscription. Use “Manage billing” to change plan or payment method.")
        customer_id = clinic.get("stripe_customer_id")
        if not customer_id:
            cust = stripe.Customer.create(email=user["email"], name=clinic["name"], metadata={"clinic_id": clinic["clinic_id"]})
            customer_id = cust.id
            await db.clinics.update_one({"clinic_id": user["clinic_id"]}, {"$set": {"stripe_customer_id": customer_id}})
        trial_days = 0
        if clinic.get("trial_ends_at") and not clinic.get("stripe_subscription_id"):
            left = datetime.fromisoformat(clinic["trial_ends_at"].replace("Z", "+00:00")) - datetime.now(timezone.utc)
            trial_days = max(0, min(14, left.days))
        return clinic, customer_id, trial_days

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
    async def checkout(req: CheckoutReq, request: Request, user=Depends(auth_dep)):
        clinic, customer_id, trial_days = await prepare_checkout(user)
        prices = stripe.Price.list(lookup_keys=[req.lookup_key], active=True, limit=1).data
        if not prices:
            raise HTTPException(400, f"Plan not found: {req.lookup_key}")
        price = prices[0]

        origin = safe_origin(req.origin_url, request)
        sub_data = {"metadata": {"clinic_id": clinic["clinic_id"], "lookup_key": req.lookup_key}}
        if trial_days > 0:
            sub_data["trial_period_days"] = trial_days
        kwargs = dict(
            customer=customer_id,
            line_items=[{"price": price.id, "quantity": 1}],
            mode="subscription",
            success_url=f"{origin}/payment/success?session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=f"{origin}/app/billing",
            metadata={"clinic_id": clinic["clinic_id"], "lookup_key": req.lookup_key},
            subscription_data=sub_data,
        )

        tax_mode = get_tax_mode()
        session = None
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
            raise

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

    @stripe_router.post("/payments/checkout-bundle")
    async def checkout_bundle(req: BundleCheckoutReq, request: Request, user=Depends(auth_dep)):
        """Attach the Scribe add-on to any core plan in a single checkout with a 20% bundle discount."""
        clinic, customer_id, trial_days = await prepare_checkout(user)
        core = stripe.Price.list(lookup_keys=[req.core_lookup_key], active=True, limit=1).data
        if not core:
            raise HTTPException(400, f"Plan not found: {req.core_lookup_key}")
        core_price = core[0]
        line_items = [{"price": core_price.id, "quantity": 1}]

        applied_bundle = False
        if req.attach_scribe:
            scribe = stripe.Price.list(lookup_keys=["vetaura_scribe_addon_monthly"], active=True, limit=1).data
            if not scribe:
                raise HTTPException(503, "The Scribe add-on isn't available right now. Please try again shortly.")
            qty = max(1, min(20, int(req.scribe_quantity or 1)))
            line_items.append({"price": scribe[0].id, "quantity": qty})
            applied_bundle = True
        origin = safe_origin(req.origin_url, request)
        sub_data = {"metadata": {"clinic_id": clinic["clinic_id"], "lookup_key": req.core_lookup_key}}
        if trial_days > 0:
            sub_data["trial_period_days"] = trial_days
        kwargs = dict(
            customer=customer_id,
            line_items=line_items,
            mode="subscription",
            success_url=f"{origin}/payment/success?session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=f"{origin}/app/billing",
            metadata={"clinic_id": clinic["clinic_id"], "lookup_key": req.core_lookup_key, "bundle": "1" if applied_bundle else "0"},
            subscription_data=sub_data,
        )
        if applied_bundle:
            kwargs["discounts"] = [{"coupon": BUNDLE_COUPON_ID}]

        tax_mode = get_tax_mode()
        session = None
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
            logger.error(f"Stripe bundle checkout error: {e}")
            raise

        await db.payment_transactions.insert_one({
            "session_id": session.id,
            "clinic_id": clinic["clinic_id"],
            "lookup_key": req.core_lookup_key,
            "bundle": applied_bundle,
            "amount": core_price.unit_amount,
            "currency": core_price.currency,
            "status": "initiated",
            "payment_status": "pending",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        })
        return {"checkout_url": session.url, "session_id": session.id, "bundle_applied": applied_bundle}

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
                    if record.get("clinic_id") and s.subscription:
                        plan = record.get("lookup_key", "").replace("vetaura_", "").split("_")[0] or "starter"
                        await sync_subscription(stripe.Subscription.retrieve(s.subscription), record["clinic_id"], plan)
                    record = await db.payment_transactions.find_one({"session_id": session_id}, {"_id": 0})
            except stripe.error.StripeError:
                pass
        return {"session_id": record["session_id"], "status": record["status"], "payment_status": record["payment_status"]}

    @stripe_router.post("/payments/portal")
    async def billing_portal(req: dict, request: Request, user=Depends(auth_dep)):
        if user.get("role", "owner") != "owner":
            raise HTTPException(403, "Only clinic owners can manage the subscription.")
        clinic = await db.clinics.find_one({"clinic_id": user["clinic_id"]}, {"_id": 0})
        if not clinic.get("stripe_customer_id"):
            raise HTTPException(400, "No billing account yet")
        origin_url = safe_origin(req.get("origin_url", ""), request)
        portal = stripe.billing_portal.Session.create(
            customer=clinic["stripe_customer_id"],
            return_url=f"{origin_url}/app/billing",
        )
        return {"portal_url": portal.url}

    @stripe_router.post("/stripe/webhook")
    async def webhook(request: Request):
        payload = await request.body()
        sig = request.headers.get("stripe-signature", "")
        try:
            event = stripe.Webhook.construct_event(payload, sig, STRIPE_WEBHOOK_SECRET)
        except Exception:
            raise HTTPException(400, "Invalid signature")

        obj, t = event["data"]["object"], event["type"]
        try:
            await db.stripe_events.insert_one({"_id": event["id"], "type": t, "at": datetime.now(timezone.utc).isoformat()})
        except Exception:
            return {"status": "duplicate"}
        try:
            if t == "checkout.session.completed":
                await db.payment_transactions.update_one(
                    {"session_id": obj["id"], "payment_status": {"$ne": "paid"}},
                    {"$set": {"status": "completed", "payment_status": obj.get("payment_status", "paid"),
                              "stripe_subscription_id": obj.get("subscription"),
                              "updated_at": datetime.now(timezone.utc).isoformat()}})
                clinic_id = (obj.get("metadata") or {}).get("clinic_id")
                plan = (obj.get("metadata") or {}).get("lookup_key", "").replace("vetaura_", "").split("_")[0] or "starter"
                if clinic_id and obj.get("subscription"):
                    await sync_subscription(stripe.Subscription.retrieve(obj["subscription"]), clinic_id, plan)
            elif t in ("customer.subscription.created", "customer.subscription.updated", "customer.subscription.deleted",
                       "customer.subscription.paused", "customer.subscription.resumed"):
                await sync_subscription(obj)
            elif t == "customer.subscription.trial_will_end":
                await sync_subscription(obj)
                await db.clinics.update_one({"stripe_subscription_id": obj["id"]}, {"$set": {
                    "billing_notice": f"Your free trial ends on {_iso(obj['trial_end'])[:10]}. Your card will be charged then."}})
            elif t in ("invoice.paid", "invoice.payment_failed", "invoice.payment_action_required"):
                sub_id = _sub_id_from_invoice(obj)
                if sub_id:
                    await sync_subscription(stripe.Subscription.retrieve(sub_id))
                if t != "invoice.paid" and sub_id:
                    await db.clinics.update_one({"stripe_subscription_id": sub_id}, {"$set": {
                        "billing_notice": "Your last payment didn't go through. Update your card in Manage billing to avoid losing access."}})
        except Exception as e:
            await db.stripe_events.delete_one({"_id": event["id"]})
            logger.exception(f"Stripe webhook {t} failed: {e}")
            raise HTTPException(500, "Webhook processing failed")
        return {"status": "ok"}

    return stripe_router
