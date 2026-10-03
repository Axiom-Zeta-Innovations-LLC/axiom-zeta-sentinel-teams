# Stripe Billing — Auto API Key Provisioning

Axiom Zeta Sentinel Solo / Teams / Sovereign share this flow.

## Flow
1. Customer clicks a Stripe checkout link (from axiomzeta-innovations.com products page, Sentinel section) or calls `POST /v1/billing/checkout {tier, email}` on a gateway.
2. Stripe Checkout (subscription mode) collects payment. Prices come from env: `STRIPE_PRICE_SOLO`, `STRIPE_PRICE_TEAMS`, `STRIPE_PRICE_SOVEREIGN`.
3. Stripe sends `checkout.session.completed` to `POST /v1/billing/webhook` (signed with `STRIPE_WEBHOOK_SECRET`).
4. Webhook provisions access automatically: Solo gets a tenant record + `azs_...` API key; Teams/Sovereign get org + workspace + workspace API key.
5. Customer retrieves key once via `GET /v1/billing/session/{checkout_session_id}` or GUI Billing panel.
6. `customer.subscription.deleted` revokes key. Portal via `POST /v1/billing/portal`.

## Env
STRIPE_SECRET_KEY, STRIPE_WEBHOOK_SECRET, STRIPE_PRICE_SOLO/TEAMS/SOVEREIGN, PUBLIC_BASE_URL.

## Site wiring (axiomzeta-innovations.com)
Sentinel CTAs read NEXT_PUBLIC_SENTINEL_SOLO_CHECKOUT_URL / TEAMS / SOVEREIGN. Unset = fallback to section/contact, no dead links.

## Not yet verified
Real Stripe test-mode checkout to webhook to key use needs connected Stripe account + deployed public webhook URL. Local tests cover config, 503 without key, signed webhook provisioning, one-time reveal.
