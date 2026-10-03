from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import requests

from .types import FeedbackResponse, StabilizeResponse, TelemetryResponse


@dataclass
class AxiomZetaSentinelClient:
    base_url: str = "http://127.0.0.1:8000"
    api_key: str | None = None
    timeout_seconds: float = 20.0
    # Team/Enterprise: authenticate as a workspace instead of with the gateway admin key.
    workspace_key_id: str | None = None
    workspace_key: str | None = None

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.workspace_key_id and self.workspace_key:
            headers["X-Workspace-Key-Id"] = self.workspace_key_id
            headers["X-Workspace-Key"] = self.workspace_key
        elif self.api_key:
            headers["X-API-Key"] = self.api_key
        return headers

    def reset_baseline(self, *, tenant_id: str) -> dict[str, Any]:
        """Forget the tenant's learned reference baseline (after an intended change)."""
        res = requests.post(
            f"{self.base_url}/v1/baseline/reset",
            json={"tenant_id": tenant_id},
            headers=self._headers(),
            timeout=self.timeout_seconds,
        )
        res.raise_for_status()
        return res.json()

    def stabilize(
        self,
        *,
        tenant_id: str,
        request_id: str,
        metric_window: list[float],
        text: str | None = None,
        embedding: list[float] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> StabilizeResponse:
        payload = {
            "tenant_id": tenant_id,
            "request_id": request_id,
            "text": text,
            "embedding": embedding,
            "metric_window": metric_window,
            "metadata": metadata or {},
        }
        res = requests.post(
            f"{self.base_url}/v1/stabilize",
            json=payload,
            headers=self._headers(),
            timeout=self.timeout_seconds,
        )
        res.raise_for_status()
        return res.json()

    def feedback(
        self,
        *,
        tenant_id: str,
        request_id: str,
        corrected: bool,
        correction_score: float,
        observed_risk_level: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> FeedbackResponse:
        payload = {
            "tenant_id": tenant_id,
            "request_id": request_id,
            "corrected": corrected,
            "correction_score": correction_score,
            "observed_risk_level": observed_risk_level,
            "metadata": metadata or {},
        }
        res = requests.post(
            f"{self.base_url}/v1/feedback",
            json=payload,
            headers=self._headers(),
            timeout=self.timeout_seconds,
        )
        res.raise_for_status()
        return res.json()

    def telemetry(self, format: str = "json") -> TelemetryResponse | str:
        res = requests.get(
            f"{self.base_url}/v1/telemetry",
            params={"format": format},
            headers=self._headers(),
            timeout=self.timeout_seconds,
        )
        res.raise_for_status()
        if format == "prometheus":
            return res.text
        return res.json()

    def health(self) -> dict[str, Any]:
        res = requests.get(
            f"{self.base_url}/v1/health",
            headers=self._headers(),
            timeout=self.timeout_seconds,
        )
        res.raise_for_status()
        return res.json()
