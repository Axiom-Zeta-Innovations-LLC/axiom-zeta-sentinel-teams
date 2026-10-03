from __future__ import annotations
import hashlib, hmac, json, os, time, urllib.request, urllib.parse
from dataclasses import dataclass, field
from threading import Lock
from secrets import token_urlsafe

def _env(k, d=""): return os.getenv(k, d).strip()

@dataclass
class BillingRecord:
    customer_id: str
    email: str | None
    tier: str
    tenant_id: str
    workspace_id: str | None = None
    org_id: str | None = None
    api_key_id: str | None = None
    api_key_hash: str | None = None
    raw_key_once: str | None = None  # only kept until retrieved via session lookup
    checkout_session_id: str | None = None
    subscription_id: str | None = None
    status: str = "pending"

class BillingStore:
    def __init__(self):
        self._lock=Lock(); self._by_session={}; self._by_customer={}; self._by_key_hash={}
    def put(self, rec: BillingRecord):
        with self._lock:
            if rec.checkout_session_id: self._by_session[rec.checkout_session_id]=rec
            self._by_customer[rec.customer_id]=rec
            if rec.api_key_hash: self._by_key_hash[rec.api_key_hash]=rec
    def by_session(self, sid): 
        with self._lock: return self._by_session.get(sid)
    def by_customer(self, cid):
        with self._lock: return self._by_customer.get(cid)
    def revoke_customer(self, cid):
        with self._lock:
            rec=self._by_customer.get(cid)
            if rec:
                rec.status="canceled"
                if rec.api_key_hash: self._by_key_hash.pop(rec.api_key_hash, None)
            return rec
    def is_valid_billing_key(self, raw):
        if not raw: return None
        h=hashlib.sha256(raw.encode()).hexdigest()
        with self._lock: 
            rec=self._by_key_hash.get(h)
            return rec if rec and rec.status in ("active","trialing","pending") else None

billing_store=BillingStore()

def price_for_tier(tier: str) -> str | None:
    mapping={"solo":_env("STRIPE_PRICE_SOLO"),"teams":_env("STRIPE_PRICE_TEAMS"),"sovereign":_env("STRIPE_PRICE_SOVEREIGN")}
    return mapping.get(tier.lower()) or None

def stripe_configured() -> bool:
    return bool(_env("STRIPE_SECRET_KEY"))

def _stripe_post(path: str, form: dict) -> dict:
    secret=_env("STRIPE_SECRET_KEY")
    if not secret: raise RuntimeError("STRIPE_SECRET_KEY not configured")
    data=urllib.parse.urlencode(form, doseq=True).encode()
    req=urllib.request.Request("https://api.stripe.com/v1"+path, data=data, method="POST")
    req.add_header("Authorization", f"Bearer {secret}")
    req.add_header("Content-Type","application/x-www-form-urlencoded")
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode())

def create_checkout_session(*, tier: str, email: str | None, success_url: str, cancel_url: str, client_reference_id: str | None=None) -> dict:
    price=price_for_tier(tier)
    if not price: raise RuntimeError(f"No Stripe price configured for tier {tier} (set STRIPE_PRICE_*)")
    form={"mode":"subscription","success_url":success_url,"cancel_url":cancel_url,"line_items[0][price]":price,"line_items[0][quantity]":1,"metadata[tier]":tier}
    if email: form["customer_email"]=email
    if client_reference_id: form["client_reference_id"]=client_reference_id
    return _stripe_post("/checkout/sessions", form)

def create_portal_session(*, customer_id: str, return_url: str) -> dict:
    return _stripe_post("/billing_portal/sessions", {"customer":customer_id,"return_url":return_url})

def verify_webhook(raw_body: bytes, sig_header: str | None, secret: str, tolerance: int=300) -> dict:
    if not secret: raise ValueError("STRIPE_WEBHOOK_SECRET not configured")
    if not sig_header: raise ValueError("Missing Stripe-Signature")
    parts=dict(p.split("=",1) for p in sig_header.split(",") if "=" in p)
    ts=parts.get("t"); v1=parts.get("v1")
    if not ts or not v1: raise ValueError("Invalid Stripe-Signature")
    if abs(time.time()-int(ts))>tolerance: raise ValueError("Webhook timestamp outside tolerance")
    signed=f"{ts}.".encode()+raw_body
    expected=hmac.new(secret.encode(), signed, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, v1): raise ValueError("Invalid webhook signature")
    return json.loads(raw_body.decode())

def new_api_key() -> str:
    return "azs_"+token_urlsafe(24)
