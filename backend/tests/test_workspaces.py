import pytest
import uuid
from models import Workspace, WorkspaceMember


@pytest.mark.asyncio
async def test_create_workspace(client, mock_user):
    r = await client.post("/workspaces", json={"name": "My Workspace"})
    assert r.status_code == 201
    data = r.json()
    assert data["name"] == "My Workspace"
    assert data["owner_id"] == mock_user
    assert "id" in data


@pytest.mark.asyncio
async def test_create_workspace_requires_auth(client):
    r = await client.post("/workspaces", json={"name": "Test"})
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_list_workspaces_returns_own(client, mock_user):
    await client.post("/workspaces", json={"name": "WS-A"})
    await client.post("/workspaces", json={"name": "WS-B"})
    r = await client.get("/workspaces")
    assert r.status_code == 200
    names = {ws["name"] for ws in r.json()}
    assert "WS-A" in names
    assert "WS-B" in names


@pytest.mark.asyncio
async def test_create_workspace_reports_creator_as_admin(client, mock_user):
    r = await client.post("/workspaces", json={"name": "Mine"})
    assert r.json()["role"] == "admin"


@pytest.mark.asyncio
async def test_list_workspaces_reports_callers_own_role(client, auth_as, db_session):
    """`role` is per-caller, not per-workspace: the same workspace reports
    "admin" to its owner and "viewer" to a viewer. The UI gates the HITL
    approve control on it, so a wrong role here means a guaranteed 403."""
    auth_as("owner@example.com")
    ws_id = (await client.post("/workspaces", json={"name": "Shared"})).json()["id"]
    await client.post(f"/workspaces/{ws_id}/members", json={"user_id": "viewer@example.com", "role": "viewer"})

    owner_view = await client.get("/workspaces")
    assert [ws["role"] for ws in owner_view.json() if ws["id"] == ws_id] == ["admin"]

    auth_as("viewer@example.com")
    viewer_view = await client.get("/workspaces")
    assert [ws["role"] for ws in viewer_view.json() if ws["id"] == ws_id] == ["viewer"]


@pytest.mark.asyncio
async def test_auto_created_personal_workspace_is_admin(client, auth_as):
    """A user with no workspaces gets "Personal" auto-created — as its admin,
    not as a roleless row the UI would have to guess about."""
    auth_as("brand-new@example.com")
    r = await client.get("/workspaces")
    assert r.status_code == 200
    assert [ws["role"] for ws in r.json()] == ["admin"]


@pytest.mark.asyncio
async def test_list_workspaces_does_not_return_others(client, auth_as, db_session):
    # Workspace owned by a different user with no membership for mock_user
    other_ws = Workspace(name="Other WS", owner_id="other-user-abc")
    db_session.add(other_ws)
    await db_session.commit()

    auth_as("test-user-123")
    r = await client.get("/workspaces")
    assert r.status_code == 200
    names = [ws["name"] for ws in r.json()]
    assert "Other WS" not in names


@pytest.mark.asyncio
async def test_add_member_as_owner(client, mock_user):
    ws_resp = await client.post("/workspaces", json={"name": "Team WS"})
    ws_id = ws_resp.json()["id"]

    r = await client.post(f"/workspaces/{ws_id}/members", json={"user_id": "new-member", "role": "viewer"})
    assert r.status_code == 201
    data = r.json()
    assert data["user_id"] == "new-member"
    assert data["role"] == "viewer"


@pytest.mark.asyncio
async def test_add_member_non_owner_forbidden(client, auth_as, db_session):
    owner = "real-owner"
    ws = Workspace(name="Private WS", owner_id=owner)
    db_session.add(ws)
    await db_session.flush()
    db_session.add(WorkspaceMember(workspace_id=ws.id, user_id=owner, role="admin"))
    await db_session.commit()

    auth_as("not-the-owner")
    r = await client.post(f"/workspaces/{ws.id}/members", json={"user_id": "someone", "role": "viewer"})
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_add_member_invalid_role(client, mock_user):
    ws_resp = await client.post("/workspaces", json={"name": "WS"})
    ws_id = ws_resp.json()["id"]
    r = await client.post(f"/workspaces/{ws_id}/members", json={"user_id": "user", "role": "superadmin"})
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_remove_member_as_owner(client, mock_user, db_session):
    ws_resp = await client.post("/workspaces", json={"name": "WS"})
    ws_id = ws_resp.json()["id"]
    await client.post(f"/workspaces/{ws_id}/members", json={"user_id": "to-remove", "role": "viewer"})

    r = await client.delete(f"/workspaces/{ws_id}/members/to-remove")
    assert r.status_code == 204


@pytest.mark.asyncio
async def test_remove_member_non_owner_forbidden(client, auth_as, db_session):
    owner = "real-owner-2"
    ws = Workspace(name="Private WS", owner_id=owner)
    db_session.add(ws)
    await db_session.flush()
    db_session.add(WorkspaceMember(workspace_id=ws.id, user_id=owner, role="admin"))
    db_session.add(WorkspaceMember(workspace_id=ws.id, user_id="victim", role="viewer"))
    await db_session.commit()

    auth_as("not-the-owner")
    r = await client.delete(f"/workspaces/{ws.id}/members/victim")
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_admin_member_can_manage_the_roster(client, auth_as, db_session):
    """The `admin` rung of _ROLE_RANK has to mean something.

    Member management used to check ownership only, so promoting someone to
    admin granted them the label and nothing else — the workspace still had
    exactly one person who could add or remove anyone.
    """
    owner, admin = "roster-owner", "promoted-admin"
    ws = Workspace(name="Delegated WS", owner_id=owner)
    db_session.add(ws)
    await db_session.flush()
    db_session.add_all([
        WorkspaceMember(workspace_id=ws.id, user_id=owner, role="admin"),
        WorkspaceMember(workspace_id=ws.id, user_id=admin, role="admin"),
        WorkspaceMember(workspace_id=ws.id, user_id="victim", role="viewer"),
    ])
    await db_session.commit()

    auth_as(admin)
    assert (await client.post(
        f"/workspaces/{ws.id}/members", json={"user_id": "recruit", "role": "operator"}
    )).status_code == 201
    assert (await client.delete(f"/workspaces/{ws.id}/members/victim")).status_code == 204
    # …but the owner's claim on the workspace is not the admin's to revoke.
    assert (await client.delete(f"/workspaces/{ws.id}/members/{owner}")).status_code == 400


@pytest.mark.asyncio
async def test_operator_member_cannot_manage_the_roster(client, auth_as, db_session):
    """Only the top rung manages members — being *in* the workspace isn't enough."""
    ws = Workspace(name="Operator WS", owner_id="op-owner")
    db_session.add(ws)
    await db_session.flush()
    db_session.add_all([
        WorkspaceMember(workspace_id=ws.id, user_id="op-owner", role="admin"),
        WorkspaceMember(workspace_id=ws.id, user_id="an-operator", role="operator"),
    ])
    await db_session.commit()

    auth_as("an-operator")
    add = await client.post(f"/workspaces/{ws.id}/members", json={"user_id": "x", "role": "viewer"})
    assert add.status_code == 403
    assert (await client.delete(f"/workspaces/{ws.id}/members/op-owner")).status_code == 403


@pytest.mark.asyncio
async def test_managing_a_nonexistent_workspace_reveals_nothing(client, auth_as):
    """Same 403 as an unauthorized workspace, so the response can't be used to
    probe which workspace IDs exist."""
    auth_as("prober")
    r = await client.post(f"/workspaces/{uuid.uuid4()}/members", json={"user_id": "x", "role": "viewer"})
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_list_workspaces_auto_provisions_personal(client, mock_user):
    # A user with no workspaces gets a "Personal" one created on first list.
    r = await client.get("/workspaces")
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 1
    assert data[0]["name"] == "Personal"
    assert data[0]["owner_id"] == mock_user


@pytest.mark.asyncio
async def test_list_members_returns_roster(client, mock_user):
    ws_id = (await client.post("/workspaces", json={"name": "Team"})).json()["id"]
    await client.post(f"/workspaces/{ws_id}/members", json={"user_id": "member-x", "role": "operator"})
    r = await client.get(f"/workspaces/{ws_id}/members")
    assert r.status_code == 200
    roster = {m["user_id"]: m["role"] for m in r.json()}
    assert roster[mock_user] == "admin"
    assert roster["member-x"] == "operator"


@pytest.mark.asyncio
async def test_list_members_non_member_gets_404(client, auth_as, db_session):
    ws = Workspace(name="Secret", owner_id="owner-9")
    db_session.add(ws)
    await db_session.flush()
    db_session.add(WorkspaceMember(workspace_id=ws.id, user_id="owner-9", role="admin"))
    await db_session.commit()

    auth_as("stranger")
    r = await client.get(f"/workspaces/{ws.id}/members")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_add_member_is_idempotent_and_updates_role(client, mock_user):
    ws_id = (await client.post("/workspaces", json={"name": "WS"})).json()["id"]
    first = await client.post(f"/workspaces/{ws_id}/members", json={"user_id": "m", "role": "viewer"})
    second = await client.post(f"/workspaces/{ws_id}/members", json={"user_id": "m", "role": "operator"})
    assert first.status_code == 201
    assert second.status_code == 201  # no PK-conflict crash
    roster = {m["user_id"]: m["role"] for m in (await client.get(f"/workspaces/{ws_id}/members")).json()}
    assert roster["m"] == "operator"


@pytest.mark.asyncio
async def test_owner_cannot_be_removed(client, mock_user):
    ws_id = (await client.post("/workspaces", json={"name": "WS"})).json()["id"]
    r = await client.delete(f"/workspaces/{ws_id}/members/{mock_user}")
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_list_verticals_returns_all(client):
    r = await client.get("/verticals")
    assert r.status_code == 200
    verticals = r.json()
    assert len(verticals) == 3
    keys = {v["key"] for v in verticals}
    assert "marketing_competitor_briefs" in keys
    assert "b2b_sales_lead_intel" in keys
    assert "founder_strategy_briefs" in keys
    for v in verticals:
        assert "display_name" in v
        assert "input_schema" in v
