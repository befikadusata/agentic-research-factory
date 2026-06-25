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
