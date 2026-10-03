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

## Live Stripe products (created 2026-10-03, livemode, account Axiom Zeta Innovations)
- Solo (Developer): product prod_VNIc337H86SRDm, price price_1UMY18RuE1b4AX4JxsdLRHvy, $59.99/month
- Teams: product prod_VNIc0oTpCnDoZf, price price_1UMY1DRuE1b4AX4JmwRcBpo0, $89.99/month
- Sovereign: product prod_VNIcYDpE4Mp4Vs, price price_1UMY1NRuE1b4AX4JPCI5qFw7, $119.99/month
Set gateway env STRIPE_PRICE_SOLO / STRIPE_PRICE_TEAMS / STRIPE_PRICE_SOVEREIGN to these price IDs. These are LIVE prices (not test mode).

## Payment Links (live, created 2026-10-03)
- Solo $59.99: https://buy.stripe.com/dRm6oJ8cw6AT3oa1KF18c0a (plink_1UMY39RuE1b4AX4Jr8d6aUTY)
- Teams $89.99: https://buy.stripe.com/3cI6oJ0K48J12k6ahb18c0b (plink_1UMY3ARuE1b4AX4JlLlGzN7k)
- Sovereign $119.99: https://buy.stripe.com/8x24gB64o2kDe2O3SN18c0c (plink_1UMY3CRuE1b4AX4JQCy6JU3C)
Site defaults to these; NEXT_PUBLIC_SENTINEL_*_CHECKOUT_URL overrides.
