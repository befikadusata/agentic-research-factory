import pytest
from uuid import uuid4
from models import Run, RunStatus, Workspace, WorkspaceMember, Document


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


@pytest.mark.asyncio
async def test_workspace_list_scoped_to_member(client, db_session, auth_as):
    owner = "owner@example.com"
    member = "member@example.com"
    outsider = "outsider@example.com"

    ws = await _create_workspace_with_member(db_session, owner, member)

    auth_as(outsider)
    resp = await client.get("/workspaces")
    assert resp.status_code == 200
    assert all(str(ws.id) != w["id"] for w in resp.json())

    auth_as(member)
    resp = await client.get("/workspaces")
    assert resp.status_code == 200
    ids = [w["id"] for w in resp.json()]
    assert str(ws.id) in ids


@pytest.mark.asyncio
async def test_owner_can_access_own_run_without_workspace(client, db_session, auth_as):
    owner = "owner@example.com"
    run = await _create_run(db_session, owner)

    auth_as(owner)
    resp = await client.get(f"/runs/{run.id}")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_create_run_rejects_non_member_workspace(client, db_session, auth_as):
    owner = "owner@example.com"
    member = "member@example.com"
    outsider = "outsider@example.com"
    ws = await _create_workspace_with_member(db_session, owner, member)

    auth_as(outsider)
    resp = await client.post(
        "/runs", json={"topic": "test", "format": "report", "workspace_id": str(ws.id)}
    )
    assert resp.status_code == 403

    result = await db_session.execute(Run.__table__.select().where(Run.workspace_id == ws.id))
    assert result.first() is None


@pytest.mark.asyncio
async def test_create_run_allows_workspace_member(client, db_session, auth_as):
    owner = "owner@example.com"
    member = "member@example.com"
    ws = await _create_workspace_with_member(db_session, owner, member)

    auth_as(member)
    resp = await client.post(
        "/runs", json={"topic": "test", "format": "report", "workspace_id": str(ws.id)}
    )
    assert resp.status_code == 201
    assert resp.json()["workspace_id"] == str(ws.id)


@pytest.mark.asyncio
async def test_create_run_rejects_doc_from_foreign_workspace(client, db_session, auth_as):
    owner = "owner@example.com"
    member = "member@example.com"
    other_owner = "other-owner@example.com"
    ws = await _create_workspace_with_member(db_session, owner, member)
    other_ws = await _create_workspace_with_member(db_session, other_owner, "other-member@example.com")

    foreign_doc = Document(
        workspace_id=other_ws.id,
        uploaded_by=other_owner,
        filename="secret.pdf",
        file_path="/tmp/secret.pdf",
        file_size_bytes=123,
    )
    db_session.add(foreign_doc)
    await db_session.commit()
    await db_session.refresh(foreign_doc)

    auth_as(member)
    resp = await client.post(
        "/runs",
        json={
            "topic": "test",
            "format": "report",
            "workspace_id": str(ws.id),
            "doc_ids": [str(foreign_doc.id)],
        },
    )
    assert resp.status_code == 403
