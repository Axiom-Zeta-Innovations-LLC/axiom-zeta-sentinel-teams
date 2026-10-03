import os
from dataclasses import dataclass


@dataclass(frozen=True)
class GatewaySettings:
    deterministic_mode: bool
    default_seed: int
    drift_spike_threshold: float
    breaker_trip_count: int
    max_metric_window: int
    max_compute_steps: int
    api_key: str | None
    allow_insecure_no_auth: bool = False
    max_tenants: int = 1000
    baseline_windows: int = 5


def _truthy(value: str) -> bool:
    return value.lower() in {"1", "true", "yes"}


def load_settings() -> GatewaySettings:
    api_key = os.getenv("GATEWAY_API_KEY")
    if api_key == "":
        api_key = None

    return GatewaySettings(
        deterministic_mode=os.getenv("DETERMINISTIC_MODE", "true").lower() in {"1", "true", "yes"},
        default_seed=int(os.getenv("DRIFT_ENGINE_SEED", "7")),
        drift_spike_threshold=float(os.getenv("DRIFT_SPIKE_THRESHOLD", "0.80")),
        breaker_trip_count=int(os.getenv("DRIFT_BREAKER_TRIP_COUNT", "3")),
        max_metric_window=int(os.getenv("MAX_METRIC_WINDOW", "4096")),
        max_compute_steps=int(os.getenv("MAX_COMPUTE_STEPS", "50000")),
        api_key=api_key,
        allow_insecure_no_auth=_truthy(os.getenv("ALLOW_INSECURE_NO_AUTH", "false")),
        max_tenants=int(os.getenv("MAX_TENANTS", "1000")),
        baseline_windows=int(os.getenv("BASELINE_WINDOWS", "5")),
    )
