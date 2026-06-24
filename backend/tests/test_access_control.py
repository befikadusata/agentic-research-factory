import pytest
from uuid import uuid4
from models import Run, RunStatus, Workspace, WorkspaceMember


# ── helpers ────────────────────────────────────────────────────────────────────

async def _create_run(db, user_id: str, workspace_id=None) -> Run:
    run = Run(
        user_id=user_id,
        topic="test topic",
        format="report",
        status=RunStatus.complete,
        final_output="# output",
        workspace_id=workspace_id,
    )
    db.add(run)
    await db.commit()
    await db.refresh(run)
    return run


async def _create_workspace_with_member(db, owner_id: str, member_id: str):
    ws = Workspace(name="test-ws", owner_id=owner_id)
    db.add(ws)
    await db.flush()
    db.add(WorkspaceMember(workspace_id=ws.id, user_id=owner_id, role="admin"))
    db.add(WorkspaceMember(workspace_id=ws.id, user_id=member_id, role="operator"))
    await db.commit()
    await db.refresh(ws)
    return ws


# ── stranger is denied ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_stranger_cannot_get_run(client, db_session, auth_as):
    owner = "owner@example.com"
    stranger = "stranger@example.com"
    run = await _create_run(db_session, owner)

    auth_as(stranger)
    resp = await client.get(f"/runs/{run.id}")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_stranger_cannot_get_md_output(client, db_session, auth_as):
    owner = "owner@example.com"
    stranger = "stranger@example.com"
    run = await _create_run(db_session, owner)

    auth_as(stranger)
    resp = await client.get(f"/runs/{run.id}/output/md")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_stranger_cannot_approve_hitl(client, db_session, auth_as):
    owner = "owner@example.com"
    stranger = "stranger@example.com"
    run = await _create_run(db_session, owner)

    auth_as(stranger)
    resp = await client.post(f"/runs/{run.id}/approve", json={})
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_stranger_cannot_stream(client, db_session, auth_as):
    owner = "owner@example.com"
    stranger = "stranger@example.com"
    run = await _create_run(db_session, owner)

    auth_as(stranger)
    resp = await client.get(f"/runs/{run.id}/stream")
    assert resp.status_code == 404


# ── workspace member is allowed ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_workspace_member_can_get_run(client, db_session, auth_as):
    owner = "owner@example.com"
    member = "member@example.com"
    ws = await _create_workspace_with_member(db_session, owner, member)
    run = await _create_run(db_session, owner, workspace_id=ws.id)

    auth_as(member)
    resp = await client.get(f"/runs/{run.id}")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_workspace_member_can_get_md_output(client, db_session, auth_as):
    owner = "owner@example.com"
    member = "member@example.com"
    ws = await _create_workspace_with_member(db_session, owner, member)
    run = await _create_run(db_session, owner, workspace_id=ws.id)

    auth_as(member)
    resp = await client.get(f"/runs/{run.id}/output/md")
    assert resp.status_code == 200


# ── workspace list is scoped ───────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_workspace_list_scoped_to_member(client, db_session, auth_as):
    owner = "owner@example.com"
    member = "member@example.com"
    outsider = "outsider@example.com"

    ws = await _create_workspace_with_member(db_session, owner, member)

    # outsider sees nothing
    auth_as(outsider)
    resp = await client.get("/workspaces")
    assert resp.status_code == 200
    assert all(str(ws.id) != w["id"] for w in resp.json())

    # member sees the workspace
    auth_as(member)
    resp = await client.get("/workspaces")
    assert resp.status_code == 200
    ids = [w["id"] for w in resp.json()]
    assert str(ws.id) in ids


# ── owner always has access ────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_owner_can_access_own_run_without_workspace(client, db_session, auth_as):
    owner = "owner@example.com"
    run = await _create_run(db_session, owner)

    auth_as(owner)
    resp = await client.get(f"/runs/{run.id}")
    assert resp.status_code == 200
