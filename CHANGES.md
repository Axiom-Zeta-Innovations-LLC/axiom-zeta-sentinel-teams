# Changes in this revision (Sept 15, 2026)

Reviewed and patched by Abby Davis. Every change below is covered by tests. The compiled engine is now exercised by `tests/test_real_engine.py`; run it with `REQUIRE_REAL_ENGINE=1` in CI so a broken build fails instead of skipping.

## Engine (`rust/`)

- **Builds now.**
  - Fixed a borrow error in `engine.rs` (`hole_create`) that stopped compilation.
  - Removed `python-source = "."` from `rust/pyproject.toml`, which made `maturin develop` fail.
- **Actually deterministic.** Switched `HashSet`/`HashMap` to `BTreeSet`/`BTreeMap`. Rust hash collections order items randomly per process, so the same seed and input used to give slightly different scores.
- **Reference-baseline drift detection.** Previously each window was z-scored in isolation, so shifts in mean and scale were invisible. Now each tenant engine learns a baseline from its first `BASELINE_WINDOWS` windows (default 5), then compares every window against it:
  - `level_shift`: mean shift in baseline standard deviations
  - `scale_shift`: log ratio of spread, minus small-sample noise
  - `psi`: Population Stability Index over 8 bins, bias-corrected for window size
  - `embedding_shift`: cosine distance to the mean baseline embedding. Uses the full vector; previously only its mean and RMS were used.
- **How the score is built.**
  - `drift_score = 0.65 * baseline_drift + 0.35 * hrm_score` once the baseline is ready.
  - During warm-up, the score is `hrm_score` alone (the original formula).
  - All components are returned in `diagnostics`.
- **New engine methods:** `reset_baseline()`, `export_baseline()`, and `import_baseline(dict)`.

Measured on synthetic streams (windows of 24 points, noise sd 0.05, 15 seeds):

| Scenario | Result |
|---|---|
| Stable stream | 0.3% red, 4.5% yellow |
| Mean shift of 1 sd | 64% red, 35% yellow |
| Mean shift of 3 sd | 100% red |

With 96-point windows: stable 0% red and 1.3% yellow; a 1 sd shift is 100% red. Mean shifts, noise changes, ×100 rescaling, and embedding topic changes all now go red. Before this revision, a 0.2 → 0.8 mean shift *lowered* the score.

## Gateway

- **Fails closed.** If `GATEWAY_API_KEY` is unset, requests get 503 unless `ALLOW_INSECURE_NO_AUTH=true` (local development only). Keys are compared in constant time.
- **Per-tenant lock** around the stateful engine, so concurrent requests can't collide.
- **`MAX_TENANTS`** (default 1000) caps in-memory engines. Past the cap, requests get 429.
- **`POST /v1/baseline/reset`** clears a tenant's baseline after an intended model or data change.
- **SDK:** added `reset_baseline()`; Team/Enterprise also get `workspace_key_id` + `workspace_key` authentication.

## Team security

- **Workspace keys are verified by secret.** Send both `X-Workspace-Key-Id` and `X-Workspace-Key`. The secret is hashed and compared to the stored hash. The key ID alone (visible in the key list) used to be accepted.
- **A valid workspace key is enough on its own.** Customers no longer need the gateway admin key.
- **Workspace keys are bound to their workspace.** Targeting a different workspace returns 403.
- **Engine state is namespaced per workspace** (`{workspace_id}:{tenant_id}`), so one caller can't poison another workspace's baseline by reusing a tenant name.
- **Signed user identities.** `X-User-Id` must come with `X-User-Signature = HMAC-SHA256(USER_ID_SIGNING_SECRET, user_id)`, which your dashboard back end computes (`gateway.core.auth.sign_user_id`). Keep that secret separate from `GATEWAY_API_KEY`. Unsigned IDs are refused unless `ALLOW_UNSIGNED_USER_ID=true`, which is safe only when a trusted proxy sets the header.
  - Before this change, any holder of the gateway key could claim to be any user, including an org owner.

## Still open

- **Token savings:** there is no token counting or trimming logic in the codebase yet. Remove "token savings" and "fewer hallucinations" claims from the UI and marketing until they're built and measured.
- **HRM value is unproven.** It's now 35% of the score. Benchmark it against `baseline_drift` alone on labeled drift data, and keep it only if it improves detection.
- **Latency is about 150 ms per call** (220-step mesh simulation), mostly spent in the HRM mesh.
- **`text` is accepted but not used** by the engine.
- **Telemetry wording:** `false_positive_total` counts "corrected while green," which is a missed detection. `drift_incidents_prevented` counts red decisions, not confirmed prevented incidents. Consider renaming both.
