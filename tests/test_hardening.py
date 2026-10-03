import dataclasses


def _setup_workspace(client, owner="owner-h", name="ws"):
    org_id = client.post("/v1/team/orgs", headers={"X-User-Id": owner}, json={"name": "Org " + name}).json()["org_id"]
    ws_id = client.post(
        f"/v1/team/orgs/{org_id}/workspaces", headers={"X-User-Id": owner}, json={"name": name}
    ).json()["workspace_id"]
    key = client.post(
        f"/v1/team/workspaces/{ws_id}/api-keys", headers={"X-User-Id": owner}, json={"name": "svc-key"}
    ).json()
    return org_id, ws_id, key["key_id"], key["api_key"]


def _payload(tenant_id="acme", workspace_id=None):
    body = {"tenant_id": tenant_id, "request_id": "req-h", "text": "x", "metric_window": [0.1] * 24, "metadata": {}}
    if workspace_id:
        body["workspace_id"] = workspace_id
    return body


def test_gateway_fails_closed_without_key(client, monkeypatch):
    monkeypatch.setenv("ALLOW_INSECURE_NO_AUTH", "false")
    assert client.post("/v1/stabilize", json=_payload()).status_code == 503


def test_workspace_key_id_alone_is_not_a_credential(client, monkeypatch):
    _, ws_id, key_id, secret = _setup_workspace(client)
    monkeypatch.setenv("GATEWAY_API_KEY", "gateway-admin")  # caller does not have it
    h = {"X-Workspace-Id": ws_id, "X-Workspace-Key-Id": key_id}
    assert client.post("/v1/stabilize", headers=h, json=_payload(workspace_id=ws_id)).status_code == 401
    bad = {**h, "X-Workspace-Key": secret + "x"}
    assert client.post("/v1/stabilize", headers=bad, json=_payload(workspace_id=ws_id)).status_code == 401
    good = {**h, "X-Workspace-Key": secret}
    assert client.post("/v1/stabilize", headers=good, json=_payload(workspace_id=ws_id)).status_code == 200


def test_workspace_key_cannot_target_another_workspace(client):
    _, ws_a, key_a, secret_a = _setup_workspace(client, name="ws-alpha")
    _, ws_b, _, _ = _setup_workspace(client, name="ws-beta")
    h = {"X-Workspace-Key-Id": key_a, "X-Workspace-Key": secret_a}
    assert client.post("/v1/stabilize", headers=h, json=_payload(workspace_id=ws_b)).status_code == 403


def test_revoked_key_rejected(client):
    _, ws_id, key_id, secret = _setup_workspace(client)
    client.delete(f"/v1/team/workspaces/{ws_id}/api-keys/{key_id}", headers={"X-User-Id": "owner-h"})
    h = {"X-Workspace-Key-Id": key_id, "X-Workspace-Key": secret}
    assert client.post("/v1/stabilize", headers=h, json=_payload()).status_code == 403


def test_engine_state_is_namespaced_per_workspace(client, app_modules):
    _, routes, _ = app_modules
    _, ws_a, key_a, secret_a = _setup_workspace(client, name="ws-alpha")
    _, ws_b, key_b, secret_b = _setup_workspace(client, name="ws-beta")
    client.post("/v1/stabilize", headers={"X-Workspace-Key-Id": key_a, "X-Workspace-Key": secret_a}, json=_payload("victim"))
    client.post("/v1/stabilize", headers={"X-Workspace-Key-Id": key_b, "X-Workspace-Key": secret_b}, json=_payload("victim"))
    tenants = set(routes.service._tenants)
    assert f"{ws_a}:victim" in tenants and f"{ws_b}:victim" in tenants


def test_signed_user_ids_required_when_secret_set(client, monkeypatch):
    from gateway.core.auth import sign_user_id

    monkeypatch.setenv("USER_ID_SIGNING_SECRET", "sign-me")
    monkeypatch.setenv("ALLOW_UNSIGNED_USER_ID", "false")
    spoof = client.post("/v1/team/orgs", headers={"X-User-Id": "alice"}, json={"name": "Spoofed"})
    assert spoof.status_code == 401
    ok = client.post(
        "/v1/team/orgs",
        headers={"X-User-Id": "alice", "X-User-Signature": sign_user_id("alice", "sign-me")},
        json={"name": "Signed"},
    )
    assert ok.status_code == 200


def test_unsigned_user_ids_refused_by_default(client, monkeypatch):
    monkeypatch.setenv("ALLOW_UNSIGNED_USER_ID", "false")
    assert client.post("/v1/team/orgs", headers={"X-User-Id": "alice"}, json={"name": "x"}).status_code == 503


def test_tenant_limit_returns_429(client, app_modules):
    _, routes, _ = app_modules
    routes.service.settings = dataclasses.replace(routes.service.settings, max_tenants=1)
    assert client.post("/v1/stabilize", json=_payload("one")).status_code == 200
    assert client.post("/v1/stabilize", json=_payload("two")).status_code == 429
