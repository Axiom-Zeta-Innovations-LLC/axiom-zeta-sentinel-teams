# Axiom Zeta Sentinel Teams

> **Sept 2026 revision:** the engine now builds, is deterministic, and compares each window against a learned reference baseline; authentication fails closed. See [CHANGES.md](CHANGES.md) for details and open items.

An API gateway middleware that helps reduce LLM/data drift using a full HRM manifold surgery runtime to stabilize noisy metric streams into a bounded 24-D representation.

## Product Shape

### 1) Core value proposition

- Input: model outputs, embeddings, metadata, and metric streams.
- Engine: 24-D mesh axiom-zeta-sentinel with topology-aware stabilization in Rust.
- Output: bounded corrected signal + drift score + risk/action policy.
- Outcome: fewer hallucination cascades, lower retraining frequency, and lower infra spend.

### 2) Commercial API contract

- `POST /v1/stabilize`
- `POST /v1/feedback`
- `POST /v1/baseline/reset`
- `GET /v1/health`
- `GET /v1/telemetry` (JSON or Prometheus text with `?format=prometheus`)

Team Edition collaboration APIs:

- `POST /v1/team/orgs`
- `POST /v1/team/orgs/{org_id}/members`
- `GET /v1/team/orgs/{org_id}/members`
- `POST /v1/team/orgs/{org_id}/workspaces`
- `POST /v1/team/workspaces/{workspace_id}/api-keys`
- `GET /v1/team/workspaces/{workspace_id}/api-keys`
- `DELETE /v1/team/workspaces/{workspace_id}/api-keys/{key_id}`
- `GET /v1/team/orgs/{org_id}/audit`

Team Edition request headers:

- `X-User-Id` + `X-User-Signature`: signed identity for team workflows (see CHANGES.md)
- `X-API-Key`: gateway admin key (`GATEWAY_API_KEY`, required; the gateway refuses requests if it is unset)
- `X-Workspace-Key-Id` + `X-Workspace-Key`: workspace credential for `/v1/stabilize`, `/v1/feedback`, `/v1/baseline/reset`

Team roles and permissions:

- `owner`: full org and workspace control
- `admin`: workspace + member management
- `analyst`: read access for team operations
- `viewer`: read-only access

Stabilize response includes:

- `stabilized_vector[24]`
- `drift_score`
- `risk_level` (`green`, `yellow`, `red`)
- `actions` (`pass`, `clamp`, `retry`, `fallback-model`, `human-review`)
- internal diagnostics over time: energy/stress EMA, drift EMA/trend, topology volatility, surgery rate

### 3) Architecture

- Rust crate (`axiom_zeta_sentinel_core`): deterministic HRM manifold runtime (mesh, Laplacian stress evolution, topology surgery), bounded output, high-throughput hot path.
- Python FastAPI gateway: auth, policy, tenant isolation, observability, integration points.
- PyO3/maturin bridge: Python invokes Rust core with near-C performance.
- Optional stream integration points: Redis/Kafka adapters can be added in gateway layer.

## How Engine Concepts Map To Product Components

- `SimplicialHRM` -> `DriftEngine`
- `state_vector (24)` -> stabilized trust vector
- `energy/genus/euler/betti` -> drift health diagnostics
- topology surgery style behavior -> adaptive correction operators
- symbolic/resonant forcing -> context + policy forcing terms

## Repository Layout

```text
gateway/
  main.py
  api/routes_stabilize.py
  core/{auth.py,config.py,policy.py,replay.py,schemas.py,service.py,telemetry.py}
  integrations/stream.py
sdk/
  pyproject.toml
  axiom_zeta_sentinel_sdk/{__init__.py,client.py,types.py}
examples/
  langchain_llamaindex_integration.py
notebooks/
  rag_benchmark_before_after.ipynb
rust/
  Cargo.toml
  pyproject.toml
  src/{lib.rs,engine.rs}
helm/axiom-zeta-sentinel-teams/
  Chart.yaml
  values.yaml
  templates/{deployment.yaml,service.yaml}
Dockerfile
```

## Quickstart

### 1) Build and install Rust extension

```bash
cd rust
python -m pip install -U pip maturin
maturin develop --release
cd ..
```

### 2) Install Python dependencies

```bash
python -m pip install -r requirements-dev.txt
python -m pip install -e .
```

### 3) Run API

```bash
uvicorn gateway.main:app --reload --port 8000
# or
axiom-zeta-sentinel-teams
```

Auth (required; the gateway refuses requests without it unless ALLOW_INSECURE_NO_AUTH=true):

```bash
export GATEWAY_API_KEY="replace-me"
```

Create local env file for compose/runtime settings:

```bash
cp .env.example .env
```

## Example request

```bash
curl -X POST "http://127.0.0.1:8000/v1/stabilize" \
  -H "X-API-Key: replace-me" \
  -H "Content-Type: application/json" \
  -d '{
    "tenant_id":"acme",
    "request_id":"req-001",
    "metric_window":[0.1,0.2,0.12,0.25,0.4,0.33,0.29,0.31,0.28,0.35,0.37,0.34,0.3,0.27,0.26,0.24,0.22,0.2,0.19,0.18,0.21,0.23,0.25,0.2],
    "embedding":[0.01,-0.02,0.03,0.04],
    "metadata":{"source":"mvp-test"}
  }'
```

Expected response shape:

```json
{
  "request_id": "req-001",
  "stabilized_vector": [0.0, 0.0, 0.0],
  "drift_score": 0.0,
  "risk_level": "green",
  "actions": ["pass"],
  "diagnostics": {
    "euler_chi": 0.0,
    "genus": 0.0,
    "beta0": 1.0,
    "beta1": 0.0,
    "energy_level": 0.0,
    "stress_level": 0.0,
    "drift_ema": 0.0,
    "drift_trend": 0.0,
    "topology_volatility": 0.0,
    "surgery_rate": 0.0,
    "surgery_total": 0.0,
    "breaker_open": 0.0,
    "spike_streak": 0.0,
    "effective_window": 24.0
  }
}
```

## Feedback and telemetry

```bash
curl -X POST "http://127.0.0.1:8000/v1/feedback" \
  -H "X-API-Key: replace-me" \
  -H "Content-Type: application/json" \
  -d '{
    "tenant_id":"acme",
    "request_id":"req-001",
    "corrected":true,
    "correction_score":0.92,
    "observed_risk_level":"green"
  }'
```

```bash
curl -H "X-API-Key: replace-me" "http://127.0.0.1:8000/v1/telemetry"
curl -H "X-API-Key: replace-me" "http://127.0.0.1:8000/v1/telemetry?format=prometheus"
```

## Python SDK

Install locally:

```bash
python -m pip install -e ./sdk
```

Use in code:

```python
from axiom_zeta_sentinel_sdk import AxiomZetaSentinelClient

client = AxiomZetaSentinelClient(base_url="http://127.0.0.1:8000", api_key="replace-me")
out = client.stabilize(
  tenant_id="acme",
  request_id="sdk-001",
  text="summarize drift",
  embedding=[0.01, -0.02, 0.04],
  metric_window=[0.2] * 24,
)
print(out["risk_level"], out["actions"])
```

## LangChain/LlamaIndex Integration

- End-to-end example script: `examples/langchain_llamaindex_integration.py`
- Integration point: post-retrieval, pre-generation middleware.
- This keeps the framework dependency optional while demonstrating action routing.

## Local Runtime With Compose

```bash
cp .env.example .env
docker compose up --build
```

Included files:

- `.env.example` for runtime configuration
- `docker-compose.yml` for local gateway orchestration

## Benchmark Notebook (RAG Before/After)

- Notebook: `notebooks/rag_benchmark_before_after.ipynb`
- Measures baseline vs stabilized hallucination proxy over synthetic drift bursts.
- Visualizes drift score and internal HRM diagnostics over time.

Run:

```bash
jupyter notebook notebooks/rag_benchmark_before_after.ipynb
```

## MVP Plan Coverage

- Refactored engine boundary: no plotting/runtime script globals in gateway runtime.
- Stable I/O schema: strict bounded Pydantic models.
- Rust hot path: stabilization dynamics and diagnostics in `axiom_zeta_sentinel_core`.
- Gateway policy layer: risk thresholds + fallback hooks + circuit-breaker escalation.
- Telemetry and SLOs: p95 latency, incidents prevented, false positives.
- Packaging: Docker image and Helm chart for drop-in deployment.

## Product Hardening Implemented

- Determinism mode and seed controls via env settings.
- Per-tenant engine isolation in service runtime.
- Circuit-breakers on repeated drift spikes.
- Replay test harness in `gateway/core/replay.py`.
- Cost controls via step caps and compute budget metadata.

## Deployment

Build container:

```bash
docker build -t axiom-zeta-sentinel-teams:latest .
```

Install Helm chart:

```bash
helm install axiom-zeta-sentinel-teams ./helm/axiom-zeta-sentinel-teams
```

## Notes

- `metric_window` must contain at least 24 values.
- Output vector is always bounded in `[-1, 1]` and length 24.
- Drift score is bounded in `[0, 1]`.
- Diagnostics now include stronger runtime metrics: `energy_level`, `stress_level`, `drift_ema`, `drift_trend`, `topology_volatility`, `surgery_rate`, `surgery_total`.

## GUI

A full single-page GUI is bundled at `gateway/static/index.html` and served by the gateway itself:

- Open `/` or `/ui` after starting the API (e.g. http://127.0.0.1:8000/ui)
- Enter your gateway API key (and workspace/user credentials on Teams/Sovereign), generate a synthetic metric window (stable / mean shift / noise / rescale), run **Stabilize**, and inspect drift score, risk, actions, 24-D stabilized vector and diagnostics.
- Teams adds org/workspace/API-key/audit/analytics panels. Sovereign adds health/OIDC/session/policy status.

No separate frontend build is required.
