# axiom_zeta_sentinel_sdk

Simple Python SDK for the Axiom Zeta Sentinel Teams Gateway.

## Quick Usage

```python
from axiom_zeta_sentinel_sdk import AxiomZetaSentinelClient

client = AxiomZetaSentinelClient(base_url="http://127.0.0.1:8000", api_key="replace-me")

out = client.stabilize(
    tenant_id="acme",
    request_id="req-42",
    text="what is the latest KPI trend",
    embedding=[0.01, -0.02, 0.03],
    metric_window=[0.2] * 24,
)

print(out["drift_score"], out["risk_level"], out["actions"])
```
