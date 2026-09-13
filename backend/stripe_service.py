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
            raise HTTPException(500, "Stripe checkout error")

        if session is None:
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

    @stripe_router.post("/payments/checkout-bundle")
    async def checkout_bundle(req: BundleCheckoutReq, user=Depends(auth_dep)):
        """Attach the Scribe add-on to any core plan in a single checkout with a 20% bundle discount."""
        core = stripe.Price.list(lookup_keys=[req.core_lookup_key], active=True, limit=1).data
        if not core:
            raise HTTPException(400, f"Plan not found: {req.core_lookup_key}")
        core_price = core[0]
        line_items = [{"price": core_price.id, "quantity": 1}]

        applied_bundle = False
        if req.attach_scribe:
            scribe = stripe.Price.list(lookup_keys=["vetaura_scribe_addon_monthly"], active=True, limit=1).data
            if not scribe:
                raise HTTPException(500, "Scribe add-on not configured")
            qty = max(1, min(20, int(req.scribe_quantity or 1)))
            line_items.append({"price": scribe[0].id, "quantity": qty})
            applied_bundle = True

        clinic = await db.clinics.find_one({"clinic_id": user["clinic_id"]}, {"_id": 0})
        customer_id = clinic.get("stripe_customer_id")
        if not customer_id:
            cust = stripe.Customer.create(email=user["email"], name=clinic["name"], metadata={"clinic_id": clinic["clinic_id"]})
            customer_id = cust.id
            await db.clinics.update_one({"clinic_id": user["clinic_id"]}, {"$set": {"stripe_customer_id": customer_id}})

        trial_days = 14
        kwargs = dict(
            customer=customer_id,
            line_items=line_items,
            mode="subscription",
            success_url=f"{req.origin_url}/payment/success?session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=f"{req.origin_url}/app/billing",
            metadata={"clinic_id": clinic["clinic_id"], "lookup_key": req.core_lookup_key, "bundle": "1" if applied_bundle else "0"},
            subscription_data={"trial_period_days": trial_days, "metadata": {"clinic_id": clinic["clinic_id"]}},
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
            raise HTTPException(500, "Stripe checkout error")

        if session is None:
            raise HTTPException(500, "Stripe checkout error")

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
