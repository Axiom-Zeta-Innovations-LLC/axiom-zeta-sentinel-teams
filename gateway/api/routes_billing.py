from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from gateway.core.billing import billing_store, create_checkout_session, create_portal_session, stripe_configured, price_for_tier, BillingRecord, new_api_key, verify_webhook
import hashlib, os

router=APIRouter(prefix="/v1/billing", tags=["billing"])

class CheckoutReq(BaseModel):
    tier: str="solo"; email: str|None=None; tenant_id: str|None=None

@router.get("/config")
def config():
    return {"stripe_configured": stripe_configured(), "tiers": {t: bool(price_for_tier(t)) for t in ["solo","teams","sovereign"]}}

@router.post("/checkout")
def checkout(req: CheckoutReq):
    base=os.getenv("PUBLIC_BASE_URL","http://127.0.0.1:8000")
    try:
        sess=create_checkout_session(tier=req.tier, email=req.email, success_url=f"{base}/ui?checkout=success&session_id={{CHECKOUT_SESSION_ID}}", cancel_url=f"{base}/ui?checkout=cancel", client_reference_id=req.tenant_id)
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    return {"checkout_url": sess.get("url"), "session_id": sess.get("id")}

@router.get("/session/{session_id}")
def session_lookup(session_id: str):
    rec=billing_store.by_session(session_id)
    if not rec: raise HTTPException(status_code=404, detail="Session not provisioned yet (webhook pending)")
    out={"status":rec.status,"tier":rec.tier,"tenant_id":rec.tenant_id,"workspace_id":rec.workspace_id,"api_key":rec.raw_key_once}
    rec.raw_key_once=None  # show once
    return out

@router.post("/portal")
async def portal(request: Request):
    body=await request.json(); cid=body.get("customer_id")
    if not cid: raise HTTPException(status_code=400, detail="customer_id required")
    try:
        s=create_portal_session(customer_id=cid, return_url=os.getenv("PUBLIC_BASE_URL","http://127.0.0.1:8000")+"/ui")
    except RuntimeError as e: raise HTTPException(status_code=503, detail=str(e))
    return {"portal_url": s.get("url")}

@router.post("/webhook")
async def webhook(request: Request):
    raw=await request.body()
    try: event=verify_webhook(raw, request.headers.get("stripe-signature"), os.getenv("STRIPE_WEBHOOK_SECRET",""))
    except ValueError as e: raise HTTPException(status_code=400, detail=str(e))
    etype=event.get("type"); obj=event.get("data",{}).get("object",{})
    if etype in ("checkout.session.completed","customer.subscription.created","customer.subscription.updated"):
        customer=obj.get("customer") or "cus_unknown"; sess_id=obj.get("id") if etype.startswith("checkout") else obj.get("checkout_session") or obj.get("id")
        tier=(obj.get("metadata") or {}).get("tier","solo"); email=obj.get("customer_email") or obj.get("customer_details",{}).get("email")
        tenant=obj.get("client_reference_id") or customer
        raw_key=new_api_key()
        try:
            from gateway.core.team import team_store as _ts
            org=_ts.create_org(name=(email or tenant)+" org", created_by=email or tenant)
            ws=_ts.create_workspace(org_id=org.org_id, actor_user_id=email or tenant, name="Axiom Zeta Sentinel workspace")
            krec, kraw=_ts.create_api_key(workspace_id=ws.workspace_id, actor_user_id=email or tenant, name="stripe-provisioned")
            rec=BillingRecord(customer_id=customer,email=email,tier=tier,tenant_id=tenant,org_id=org.org_id,workspace_id=ws.workspace_id,api_key_id=krec.key_id,checkout_session_id=sess_id,subscription_id=obj.get("subscription") or (obj.get("id") if "subscription" in etype else None),api_key_hash=hashlib.sha256(kraw.encode()).hexdigest(),raw_key_once=kraw,status="active")
        except Exception:
            rec=BillingRecord(customer_id=customer,email=email,tier=tier,tenant_id=tenant,checkout_session_id=sess_id,subscription_id=obj.get("subscription") or (obj.get("id") if "subscription" in etype else None),api_key_hash=hashlib.sha256(raw_key.encode()).hexdigest(),raw_key_once=raw_key,status="active")
        billing_store.put(rec)
        return {"received":True,"provisioned":True}
    if etype in ("customer.subscription.deleted",):
        cid=obj.get("customer"); billing_store.revoke_customer(cid); return {"received":True,"revoked":True}
    return {"received":True}
