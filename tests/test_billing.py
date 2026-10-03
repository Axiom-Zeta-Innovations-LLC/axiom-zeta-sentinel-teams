import hashlib, hmac, json, os, time
def _sign(body: bytes, secret: str):
    ts=str(int(time.time())); sig=hmac.new(secret.encode(), f"{ts}.".encode()+body, hashlib.sha256).hexdigest(); return f"t={ts},v1={sig}"
def test_billing_config(client):
    r=client.get("/v1/billing/config"); assert r.status_code==200; assert "tiers" in r.json()
def test_checkout_requires_stripe(client, monkeypatch):
    monkeypatch.delenv("STRIPE_SECRET_KEY", raising=False); monkeypatch.delenv("STRIPE_PRICE_SOLO", raising=False)
    r=client.post("/v1/billing/checkout", json={"tier":"solo","email":"a@b.c"}); assert r.status_code==503
def test_webhook_provisions_key(client, monkeypatch):
    secret="whsec_test"; monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", secret)
    body=json.dumps({"type":"checkout.session.completed","data":{"object":{"id":"cs_test_1","customer":"cus_test_1","customer_email":"a@b.c","metadata":{"tier":"solo"},"subscription":"sub_1"}}}).encode()
    r=client.post("/v1/billing/webhook", content=body, headers={"stripe-signature":_sign(body,secret)})
    assert r.status_code==200
    r2=client.get("/v1/billing/session/cs_test_1"); assert r2.status_code==200; assert r2.json()["api_key"].startswith("azs_")
