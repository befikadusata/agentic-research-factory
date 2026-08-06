import unittest.mock

import pytest

from models import Run, RunStatus, Workspace, WorkspaceMember


async def _create_run(
    db,
    user_id: str,
    status: RunStatus,
    final_output: str | None = None,
    format: str = "report",
) -> str:
    run = Run(
        user_id=user_id,
        topic="Test topic",
        format=format,
        status=status,
        final_output=final_output,
        doc_paths=[],
    )
    db.add(run)
    await db.commit()
    await db.refresh(run)
    return str(run.id)


async def _create_workspace_run(db, owner_id: str, member_id: str, member_role: str, status: RunStatus) -> str:
    ws = Workspace(name="test-ws", owner_id=owner_id)
    db.add(ws)
    await db.flush()
    db.add(WorkspaceMember(workspace_id=ws.id, user_id=owner_id, role="admin"))
    db.add(WorkspaceMember(workspace_id=ws.id, user_id=member_id, role=member_role))
    run = Run(
        user_id=owner_id, topic="Test topic", format="report",
        status=status, workspace_id=ws.id, doc_paths=[],
    )
    db.add(run)
    await db.commit()
    await db.refresh(run)
    return str(run.id)


@pytest.mark.asyncio
@pytest.mark.parametrize("pause_status", [
    RunStatus.awaiting_research_approval,
    RunStatus.awaiting_analysis_approval,
    RunStatus.awaiting_final_approval,
])
async def test_hitl_approve_requires_ownership(client, auth_as, db_session, pause_status):
    owner_id = "owner@example.com"
    other_id = "other@example.com"
    run_id = await _create_run(db_session, owner_id, pause_status)

    auth_as(other_id)
    denied = await client.post(f"/runs/{run_id}/approve", json={"instruction": "continue"})
    assert denied.status_code == 404

    auth_as(owner_id)
    allowed = await client.post(f"/runs/{run_id}/approve", json={"instruction": "continue"})
    assert allowed.status_code == 200
    assert allowed.json()["status"] == "resumed"


@pytest.mark.asyncio
async def test_hitl_approve_no_instruction(client, auth_as, db_session):
    owner_id = "owner@example.com"
    run_id = await _create_run(db_session, owner_id, RunStatus.awaiting_analysis_approval)

    auth_as(owner_id)
    response = await client.post(f"/runs/{run_id}/approve", json={})
    assert response.status_code == 200
    assert response.json()["status"] == "resumed"


@pytest.mark.asyncio
async def test_hitl_approve_rejects_invalid_status(client, auth_as, db_session):
    owner_id = "owner@example.com"
    run_id = await _create_run(db_session, owner_id, RunStatus.researching)

    auth_as(owner_id)
    response = await client.post(f"/runs/{run_id}/approve", json={"instruction": "continue"})
    assert response.status_code == 400
    assert "not awaiting HITL" in response.text


@pytest.mark.asyncio
async def test_hitl_approve_denies_viewer_role(client, auth_as, db_session):
    """assert_run_access must read WorkspaceMember.role, not just membership.
    Ignoring it lets a "viewer" approve/resume a HITL-gated run with an
    arbitrary instruction, exactly as an admin can."""
    owner_id = "owner@example.com"
    viewer_id = "viewer@example.com"
    run_id = await _create_workspace_run(
        db_session, owner_id, viewer_id, "viewer", RunStatus.awaiting_research_approval
    )

    auth_as(viewer_id)
    response = await client.post(f"/runs/{run_id}/approve", json={"instruction": "continue"})
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_hitl_approve_allows_operator_role(client, auth_as, db_session):
    owner_id = "owner@example.com"
    operator_id = "operator@example.com"
    run_id = await _create_workspace_run(
        db_session, owner_id, operator_id, "operator", RunStatus.awaiting_research_approval
    )

    auth_as(operator_id)
    response = await client.post(f"/runs/{run_id}/approve", json={"instruction": "continue"})
    assert response.status_code == 200
    assert response.json()["status"] == "resumed"


@pytest.mark.asyncio
async def test_hitl_approve_allows_admin_role(client, auth_as, db_session):
    owner_id = "owner@example.com"
    admin_id = "admin@example.com"
    run_id = await _create_workspace_run(
        db_session, owner_id, admin_id, "admin", RunStatus.awaiting_research_approval
    )

    auth_as(admin_id)
    response = await client.post(f"/runs/{run_id}/approve", json={"instruction": "continue"})
    assert response.status_code == 200
    assert response.json()["status"] == "resumed"


@pytest.mark.asyncio
async def test_outputs_enforce_ownership(client, auth_as, db_session):
    owner_id = "owner@example.com"
    other_id = "other@example.com"
    run_id = await _create_run(db_session, owner_id, RunStatus.complete, final_output="# Final report")

    auth_as(other_id)
    denied_md = await client.get(f"/runs/{run_id}/output/md")
    assert denied_md.status_code == 404

    auth_as(owner_id)
    allowed_md = await client.get(f"/runs/{run_id}/output/md")
    assert allowed_md.status_code == 200
    assert "# Final report" in allowed_md.text


@pytest.mark.asyncio
@pytest.mark.parametrize("fmt", ["md", "pdf"])
async def test_output_unavailable_on_non_complete_run(client, auth_as, db_session, fmt):
    owner_id = "owner@example.com"
    run_id = await _create_run(db_session, owner_id, RunStatus.researching)

    auth_as(owner_id)
    resp = await client.get(f"/runs/{run_id}/output/{fmt}")
    assert resp.status_code == 404


@pytest.mark.asyncio
@pytest.mark.parametrize("fmt", ["md", "pdf"])
async def test_output_none_content_returns_404(client, auth_as, db_session, fmt):
    owner_id = "owner@example.com"
    run_id = await _create_run(db_session, owner_id, RunStatus.complete, final_output=None)

    auth_as(owner_id)
    resp = await client.get(f"/runs/{run_id}/output/{fmt}")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_md_download_applies_linkedin_formatting(client, auth_as, db_session):
    """outputs.py must format run.final_output for run.format rather than
    serving it verbatim, or a format="linkedin" run downloads as raw Markdown
    ([text](url), # headers) instead of LinkedIn-safe plain text."""
    owner_id = "owner@example.com"
    run_id = await _create_run(
        db_session, owner_id, RunStatus.complete,
        final_output="# Title\n\nSee [source](https://example.com/a).",
        format="linkedin",
    )

    auth_as(owner_id)
    resp = await client.get(f"/runs/{run_id}/output/md")
    assert resp.status_code == 200
    assert "**Title**" in resp.text
    assert "#" not in resp.text
    assert "https://example.com/a" in resp.text


@pytest.mark.asyncio
async def test_md_download_report_format_is_unaffected(client, auth_as, db_session):
    owner_id = "owner@example.com"
    run_id = await _create_run(
        db_session, owner_id, RunStatus.complete,
        final_output="# Final report", format="report",
    )

    auth_as(owner_id)
    resp = await client.get(f"/runs/{run_id}/output/md")
    assert resp.status_code == 200
    assert resp.text == "# Final report"


@pytest.mark.asyncio
async def test_pdf_download_returns_pdf_content_type(client, auth_as, db_session):
    owner_id = "owner@example.com"
    run_id = await _create_run(
        db_session, owner_id, RunStatus.complete, final_output="# Report\n\nContent here."
    )

    auth_as(owner_id)

    def _fake_write_pdf(path):
        with open(path, "wb") as f:
            f.write(b"%PDF-1.4 fake")

    mock_html_instance = unittest.mock.MagicMock()
    mock_html_instance.write_pdf.side_effect = _fake_write_pdf

    with unittest.mock.patch(
        "services.pdf_service.weasyprint.HTML", return_value=mock_html_instance
    ):
        resp = await client.get(f"/runs/{run_id}/output/pdf")

    assert resp.status_code == 200
    assert "application/pdf" in resp.headers["content-type"]

