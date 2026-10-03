from fastapi import APIRouter, Depends, HTTPException

from gateway.core.auth import require_api_key, require_user_id
from gateway.core.team import team_store
from gateway.core.team_schemas import (
    AddMemberRequest,
    ApiKeyResponse,
    AuditEventResponse,
    CreateApiKeyRequest,
    CreateApiKeyResponse,
    CreateOrgRequest,
    CreateWorkspaceRequest,
    MemberResponse,
    OrgResponse,
    TeamActivityResponse,
    WorkspaceAnalyticsResponse,
    WorkspaceResponse,
)

router = APIRouter(prefix="/v1/team", tags=["team-edition"])


def _require_org_role(org_id: str, user_id: str, minimum_role: str) -> None:
    org = team_store.get_org(org_id)
    if org is None:
        raise HTTPException(status_code=404, detail="Organization not found")
    if not team_store.has_role_at_least(org_id=org_id, user_id=user_id, minimum_role=minimum_role):
        raise HTTPException(status_code=403, detail="Insufficient role for organization")


def _workspace_with_access(workspace_id: str, user_id: str, minimum_role: str):
    workspace = team_store.get_workspace(workspace_id)
    if workspace is None:
        raise HTTPException(status_code=404, detail="Workspace not found")
    if not team_store.has_role_at_least(workspace.org_id, user_id, minimum_role):
        raise HTTPException(status_code=403, detail="Insufficient role for workspace")
    return workspace


@router.post("/orgs", response_model=OrgResponse)
def create_org(
    req: CreateOrgRequest,
    _: None = Depends(require_api_key),
    user_id: str = Depends(require_user_id),
) -> OrgResponse:
    org = team_store.create_org(name=req.name, created_by=user_id)
    return OrgResponse(**org.__dict__)


@router.post("/orgs/{org_id}/members", response_model=MemberResponse)
def upsert_member(
    org_id: str,
    req: AddMemberRequest,
    _: None = Depends(require_api_key),
    user_id: str = Depends(require_user_id),
) -> MemberResponse:
    _require_org_role(org_id=org_id, user_id=user_id, minimum_role="admin")
    member = team_store.add_member(org_id=org_id, actor_user_id=user_id, user_id=req.user_id, role=req.role)
    return MemberResponse(**member.__dict__)


@router.get("/orgs/{org_id}/members", response_model=list[MemberResponse])
def list_members(
    org_id: str,
    _: None = Depends(require_api_key),
    user_id: str = Depends(require_user_id),
) -> list[MemberResponse]:
    _require_org_role(org_id=org_id, user_id=user_id, minimum_role="viewer")
    members = team_store.list_members(org_id)
    return [MemberResponse(**m.__dict__) for m in members]


@router.post("/orgs/{org_id}/workspaces", response_model=WorkspaceResponse)
def create_workspace(
    org_id: str,
    req: CreateWorkspaceRequest,
    _: None = Depends(require_api_key),
    user_id: str = Depends(require_user_id),
) -> WorkspaceResponse:
    _require_org_role(org_id=org_id, user_id=user_id, minimum_role="admin")
    workspace = team_store.create_workspace(org_id=org_id, actor_user_id=user_id, name=req.name)
    return WorkspaceResponse(**workspace.__dict__)


@router.post("/workspaces/{workspace_id}/api-keys", response_model=CreateApiKeyResponse)
def create_api_key(
    workspace_id: str,
    req: CreateApiKeyRequest,
    _: None = Depends(require_api_key),
    user_id: str = Depends(require_user_id),
) -> CreateApiKeyResponse:
    workspace = _workspace_with_access(workspace_id=workspace_id, user_id=user_id, minimum_role="admin")
    record, raw_key = team_store.create_api_key(workspace_id=workspace.workspace_id, actor_user_id=user_id, name=req.name)
    return CreateApiKeyResponse(api_key=raw_key, **record.__dict__)


@router.get("/workspaces/{workspace_id}/api-keys", response_model=list[ApiKeyResponse])
def list_api_keys(
    workspace_id: str,
    _: None = Depends(require_api_key),
    user_id: str = Depends(require_user_id),
) -> list[ApiKeyResponse]:
    _workspace_with_access(workspace_id=workspace_id, user_id=user_id, minimum_role="admin")
    keys = team_store.list_api_keys(workspace_id=workspace_id)
    return [ApiKeyResponse(**k.__dict__) for k in keys]


@router.delete("/workspaces/{workspace_id}/api-keys/{key_id}", response_model=ApiKeyResponse)
def revoke_api_key(
    workspace_id: str,
    key_id: str,
    _: None = Depends(require_api_key),
    user_id: str = Depends(require_user_id),
) -> ApiKeyResponse:
    _workspace_with_access(workspace_id=workspace_id, user_id=user_id, minimum_role="admin")
    try:
        key = team_store.revoke_api_key(workspace_id=workspace_id, key_id=key_id, actor_user_id=user_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return ApiKeyResponse(**key.__dict__)


@router.get("/orgs/{org_id}/audit", response_model=list[AuditEventResponse])
def list_audit_events(
    org_id: str,
    workspace_id: str | None = None,
    _: None = Depends(require_api_key),
    user_id: str = Depends(require_user_id),
) -> list[AuditEventResponse]:
    _require_org_role(org_id=org_id, user_id=user_id, minimum_role="viewer")
    events = team_store.list_audit_events(org_id=org_id, workspace_id=workspace_id)
    return [AuditEventResponse(**event.__dict__) for event in events]


@router.get("/workspaces/{workspace_id}/analytics", response_model=WorkspaceAnalyticsResponse)
def workspace_analytics(
    workspace_id: str,
    window_hours: int = 24,
    _: None = Depends(require_api_key),
    user_id: str = Depends(require_user_id),
) -> WorkspaceAnalyticsResponse:
    _workspace_with_access(workspace_id=workspace_id, user_id=user_id, minimum_role="analyst")
    if window_hours < 1 or window_hours > 168:
        raise HTTPException(status_code=400, detail="window_hours must be between 1 and 168")
    out = team_store.workspace_analytics(workspace_id=workspace_id, window_hours=window_hours)
    return WorkspaceAnalyticsResponse(**out)


@router.get("/orgs/{org_id}/analytics/team-activity", response_model=list[TeamActivityResponse])
def org_team_activity(
    org_id: str,
    window_hours: int = 24,
    limit: int = 100,
    _: None = Depends(require_api_key),
    user_id: str = Depends(require_user_id),
) -> list[TeamActivityResponse]:
    _require_org_role(org_id=org_id, user_id=user_id, minimum_role="analyst")
    if window_hours < 1 or window_hours > 168:
        raise HTTPException(status_code=400, detail="window_hours must be between 1 and 168")
    if limit < 1 or limit > 500:
        raise HTTPException(status_code=400, detail="limit must be between 1 and 500")
    rows = team_store.org_team_activity(org_id=org_id, window_hours=window_hours, limit=limit)
    return [TeamActivityResponse(**row.__dict__) for row in rows]