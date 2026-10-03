from typing import Any
from dataclasses import dataclass, field
from threading import Lock

from axiom_zeta_sentinel_core import DriftEngine

from gateway.core.config import GatewaySettings, load_settings
from gateway.core.policy import actions_for_risk, classify_risk, enforce_circuit_breaker
from gateway.core.schemas import StabilizeRequest, StabilizeResponse


BASELINE_DIAGNOSTIC_KEYS = (
    "baseline_ready",
    "baseline_drift",
    "level_shift",
    "scale_shift",
    "psi",
    "embedding_shift",
    "hrm_score",
)


class TenantLimitError(Exception):
    """Raised when a new tenant would exceed MAX_TENANTS."""


@dataclass
class TenantRuntime:
    engine: DriftEngine
    spike_streak: int = 0
    lock: Lock = field(default_factory=Lock)


class StabilizationService:
    def __init__(self) -> None:
        self.settings: GatewaySettings = load_settings()
        self._lock = Lock()
        self._tenants: dict[str, TenantRuntime] = {}

    def _tenant_runtime(self, tenant_id: str) -> TenantRuntime:
        with self._lock:
            runtime = self._tenants.get(tenant_id)
            if runtime is None:
                if len(self._tenants) >= self.settings.max_tenants:
                    raise TenantLimitError(
                        f"tenant limit reached (MAX_TENANTS={self.settings.max_tenants})"
                    )
                runtime = TenantRuntime(
                    engine=DriftEngine(
                        nx=18,
                        ny=18,
                        n_fields=10,
                        seed=self.settings.default_seed,
                        baseline_windows=self.settings.baseline_windows,
                    ),
                )
                self._tenants[tenant_id] = runtime
            return runtime

    def _bounded_metric_window(self, req: StabilizeRequest) -> list[float]:
        window = req.metric_window
        if len(window) > self.settings.max_metric_window:
            raise ValueError(
                f"metric_window exceeds MAX_METRIC_WINDOW={self.settings.max_metric_window}"
            )

        requested_steps = int(req.metadata.get("step_cap", len(window)))
        requested_steps = max(24, requested_steps)
        budget_steps = int(req.metadata.get("compute_budget_steps", requested_steps))
        capped_steps = min(requested_steps, budget_steps, self.settings.max_compute_steps)

        if capped_steps < 24:
            raise ValueError("compute budget must allow at least 24 steps")

        if len(window) <= capped_steps:
            return list(window)

        # Uniform downsample to honor cost controls while keeping bounded behavior.
        span = len(window) - 1
        out: list[float] = []
        for i in range(capped_steps):
            idx = round(i * span / (capped_steps - 1))
            out.append(float(window[idx]))
        return out

    def stabilize(self, req: StabilizeRequest, tenant_key: str | None = None) -> StabilizeResponse:
        # tenant_key lets the caller namespace engine state (e.g. per workspace) so one
        # caller can't influence another's baseline by reusing its tenant_id.
        runtime = self._tenant_runtime(tenant_key or req.tenant_id)
        metric_window = self._bounded_metric_window(req)

        # The Rust engine is stateful (&mut self); serialize calls per tenant so concurrent
        # requests can't collide inside the extension.
        with runtime.lock:
            out: dict[str, Any] = runtime.engine.stabilize(
                metric_window=metric_window,
                embedding=req.embedding,
            )

            drift_score = float(out["drift_score"])
            if drift_score >= self.settings.drift_spike_threshold:
                runtime.spike_streak += 1
            else:
                runtime.spike_streak = 0
            spike_streak = runtime.spike_streak

        risk = classify_risk(drift_score)
        breaker_open = spike_streak >= self.settings.breaker_trip_count

        actions = actions_for_risk(risk)
        actions = enforce_circuit_breaker(actions, breaker_open)

        return StabilizeResponse(
            request_id=req.request_id,
            stabilized_vector=[float(x) for x in out["stabilized_vector"]],
            drift_score=drift_score,
            risk_level=risk,
            actions=actions,
            diagnostics={
                "euler_chi": float(out.get("euler_chi", 0.0)),
                "genus": float(out.get("genus", 0.0)),
                "beta0": float(out.get("beta0", 0.0)),
                "beta1": float(out.get("beta1", 0.0)),
                "energy_level": float(out.get("energy_level", 0.0)),
                "stress_level": float(out.get("stress_level", 0.0)),
                "drift_ema": float(out.get("drift_ema", drift_score)),
                "drift_trend": float(out.get("drift_trend", 0.0)),
                "topology_volatility": float(out.get("topology_volatility", 0.0)),
                "surgery_rate": float(out.get("surgery_rate", 0.0)),
                "surgery_total": float(out.get("surgery_total", 0.0)),
                "breaker_open": 1.0 if breaker_open else 0.0,
                "spike_streak": float(spike_streak),
                "effective_window": float(len(metric_window)),
                **{key: float(out.get(key, 0.0)) for key in BASELINE_DIAGNOSTIC_KEYS},
            },
        )

    def reset_baseline(self, tenant_id: str) -> bool:
        with self._lock:
            runtime = self._tenants.get(tenant_id)
        if runtime is None:
            return False
        with runtime.lock:
            runtime.engine.reset_baseline()
            runtime.spike_streak = 0
        return True
