import pytest
import unittest.mock
from uuid import uuid4

from models import Run, RunStatus


async def _create_run(
    db,
    user_id: str,
    status: RunStatus,
    final_output: str | None = None,
) -> str:
    run = Run(
        user_id=user_id,
        topic="Test topic",
        format="report",
        status=status,
        final_output=final_output,
        doc_paths=[],
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

