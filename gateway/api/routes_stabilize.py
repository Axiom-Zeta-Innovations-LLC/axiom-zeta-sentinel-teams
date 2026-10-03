import hashlib
import hmac
from dataclasses import dataclass

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from fastapi.responses import PlainTextResponse

from gateway.core.auth import check_gateway_key, require_api_key
from gateway.core.schemas import BaselineResetRequest, FeedbackRequest, StabilizeRequest, StabilizeResponse
from gateway.core.service import StabilizationService, TenantLimitError
from gateway.core.team import team_store
from gateway.core.telemetry import telemetry_store

router = APIRouter(prefix="/v1", tags=["stabilization"])
service = StabilizationService()


def _resolve_workspace_id(request_workspace_id: str | None, header_workspace_id: str | None) -> str | None:
    if request_workspace_id and header_workspace_id and request_workspace_id != header_workspace_id:
        raise HTTPException(status_code=400, detail="workspace_id mismatch between body and header")
    return request_workspace_id or header_workspace_id


@dataclass
class CallerAccess:
    workspace_key_id: str | None  # set when authenticated by a workspace key
    workspace_id: str | None      # workspace the key is bound to


def _gateway_auth(request: Request) -> None:
    check_gateway_key(request.headers.get("x-api-key"))


def require_stabilize_access(
    request: Request,
    x_workspace_key_id: str | None = Header(default=None),
    x_workspace_key: str | None = Header(default=None),
) -> CallerAccess:
    """Accept either the gateway key or a workspace key (ID + secret).

    Workspace keys are verified by hashing the secret and comparing it to the stored
    hash; the key ID alone is not a credential because it is listed in the dashboard.
    """
    if x_workspace_key_id is None and x_workspace_key is None:
        _gateway_auth(request)
        return CallerAccess(workspace_key_id=None, workspace_id=None)

    if not x_workspace_key_id or not x_workspace_key:
        raise HTTPException(status_code=401, detail="Provide both X-Workspace-Key-Id and X-Workspace-Key")
    key = team_store.get_api_key(x_workspace_key_id)
    presented_hash = hashlib.sha256(x_workspace_key.encode("utf-8")).hexdigest()
    if key is None or not hmac.compare_digest(presented_hash, key.key_hash):
        raise HTTPException(status_code=401, detail="Invalid workspace API key")
    if key.revoked:
        raise HTTPException(status_code=403, detail="Workspace API key is revoked")
    return CallerAccess(workspace_key_id=key.key_id, workspace_id=key.workspace_id)


def _bind_workspace(access: CallerAccess, requested_workspace_id: str | None) -> str | None:
    if access.workspace_id is None:
        return requested_workspace_id
    if requested_workspace_id is not None and requested_workspace_id != access.workspace_id:
        raise HTTPException(status_code=403, detail="Workspace key does not belong to that workspace")
    return access.workspace_id


def _tenant_key(workspace_id: str | None, tenant_id: str) -> str:
    # Namespace engine state by workspace so tenants in different workspaces never share it.
    return tenant_id if workspace_id is None else f"{workspace_id}:{tenant_id}"


def _actor_user_id(x_user_id: str | None) -> str:
    if x_user_id is None or not x_user_id.strip():
        return "system"
    return x_user_id.strip()


@router.post("/stabilize", response_model=StabilizeResponse)
def stabilize(
    req: StabilizeRequest,
    access: CallerAccess = Depends(require_stabilize_access),
    x_workspace_id: str | None = Header(default=None),
    x_user_id: str | None = Header(default=None),
) -> StabilizeResponse:
    started_at = telemetry_store.start_timer()
    workspace_id = _bind_workspace(access, _resolve_workspace_id(req.workspace_id, x_workspace_id))
    x_workspace_key_id = access.workspace_key_id

    workspace = None
    if workspace_id is not None:
        workspace = team_store.get_workspace(workspace_id)
        if workspace is None:
            telemetry_store.observe_stabilize(started_at=started_at, success=False, prevented_incident=False)
            raise HTTPException(status_code=404, detail="Workspace not found")

    if req.text is None and req.embedding is None:
        telemetry_store.observe_stabilize(
            started_at=started_at,
            success=False,
            prevented_incident=False,
            org_id=None if workspace is None else workspace.org_id,
            workspace_id=None if workspace is None else workspace.workspace_id,
        )
        raise HTTPException(status_code=400, detail="Provide at least one of: text, embedding")

    try:
        out = service.stabilize(req, tenant_key=_tenant_key(workspace_id, req.tenant_id))
        prevented = "fallback-model" in out.actions or "human-review" in out.actions
        telemetry_store.observe_stabilize(
            started_at=started_at,
            success=True,
            prevented_incident=prevented,
            org_id=None if workspace is None else workspace.org_id,
            workspace_id=None if workspace is None else workspace.workspace_id,
        )
        if workspace is not None:
            team_store.record_runtime_event(
                workspace_id=workspace.workspace_id,
                actor_user_id=_actor_user_id(x_user_id),
                action="stabilize.request",
                request_id=req.request_id,
                drift_score=out.drift_score,
                prevented_incident=prevented,
                api_key_id=x_workspace_key_id,
            )
        return out
    except TenantLimitError as e:
        telemetry_store.observe_stabilize(started_at=started_at, success=False, prevented_incident=False)
        raise HTTPException(status_code=429, detail=str(e))
    except ValueError as e:
        telemetry_store.observe_stabilize(
            started_at=started_at,
            success=False,
            prevented_incident=False,
            org_id=None if workspace is None else workspace.org_id,
            workspace_id=None if workspace is None else workspace.workspace_id,
        )
        raise HTTPException(status_code=422, detail=str(e))
    except Exception:
        telemetry_store.observe_stabilize(
            started_at=started_at,
            success=False,
            prevented_incident=False,
            org_id=None if workspace is None else workspace.org_id,
            workspace_id=None if workspace is None else workspace.workspace_id,
        )
        raise HTTPException(status_code=500, detail="Internal stabilization error")


@router.post("/baseline/reset")
def reset_baseline(
    req: BaselineResetRequest,
    access: CallerAccess = Depends(require_stabilize_access),
    x_workspace_id: str | None = Header(default=None),
) -> dict[str, object]:
    """Forget a tenant's learned reference baseline (e.g. after an intended model or data change)."""
    workspace_id = _bind_workspace(access, _resolve_workspace_id(req.workspace_id, x_workspace_id))
    return {"tenant_id": req.tenant_id, "reset": service.reset_baseline(_tenant_key(workspace_id, req.tenant_id))}


@router.post("/feedback")
def feedback(
    req: FeedbackRequest,
    access: CallerAccess = Depends(require_stabilize_access),
    x_workspace_id: str | None = Header(default=None),
    x_user_id: str | None = Header(default=None),
) -> dict[str, str]:
    workspace_id = _bind_workspace(access, _resolve_workspace_id(req.workspace_id, x_workspace_id))
    workspace = None
    if workspace_id is not None:
        workspace = team_store.get_workspace(workspace_id)
        if workspace is None:
            raise HTTPException(status_code=404, detail="Workspace not found")

    telemetry_store.observe_feedback(
        corrected=req.corrected,
        risk_level=req.observed_risk_level,
        org_id=None if workspace is None else workspace.org_id,
        workspace_id=None if workspace is None else workspace.workspace_id,
    )
    if workspace is not None:
        team_store.record_runtime_event(
            workspace_id=workspace.workspace_id,
            actor_user_id=_actor_user_id(x_user_id),
            action="feedback.received",
            request_id=req.request_id,
            corrected=req.corrected,
            risk_level=req.observed_risk_level,
        )
    return {"status": "accepted", "request_id": req.request_id}


@router.get("/telemetry", response_model=None)
def telemetry(
    format: str = "json",
    workspace_id: str | None = None,
    _: None = Depends(require_api_key),
) -> object:
    org_id = None
    if workspace_id is not None:
        workspace = team_store.get_workspace(workspace_id)
        if workspace is None:
            raise HTTPException(status_code=404, detail="Workspace not found")
        org_id = workspace.org_id

    if format == "prometheus":
        return PlainTextResponse(
            telemetry_store.as_prometheus(org_id=org_id, workspace_id=workspace_id),
            media_type="text/plain; version=0.0.4",
        )

    return {
        "status": "ok",
        "metrics": telemetry_store.as_json(org_id=org_id, workspace_id=workspace_id),
    }
