import io
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from uuid import uuid4
from models import Document, DocumentStatus, Workspace, WorkspaceMember


# ── helpers ──────────────────────────────────────────────────────────────────

async def _make_workspace(db, owner_id: str) -> Workspace:
    ws = Workspace(name="test-ws", owner_id=owner_id)
    db.add(ws)
    await db.flush()  # populate ws.id before referencing it in WorkspaceMember
    db.add(WorkspaceMember(workspace_id=ws.id, user_id=owner_id, role="admin"))
    await db.commit()
    await db.refresh(ws)
    return ws


def _pdf_file(size_bytes: int = 1024):
    return {"file": ("test.pdf", io.BytesIO(b"%PDF" + b"x" * size_bytes), "application/pdf")}


# ── POST /upload ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_upload_rejects_non_pdf(client, mock_user, db_session):
    ws = await _make_workspace(db_session, mock_user)
    response = await client.post(
        f"/upload?workspace_id={ws.id}",
        files={"file": ("doc.txt", io.BytesIO(b"hello"), "text/plain")},
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_upload_rejects_oversized(client, mock_user, db_session):
    ws = await _make_workspace(db_session, mock_user)
    big = io.BytesIO(b"x" * (21 * 1024 * 1024))
    response = await client.post(
        f"/upload?workspace_id={ws.id}",
        files={"file": ("big.pdf", big, "application/pdf")},
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_upload_requires_workspace_membership(client, mock_user, db_session):
    # Workspace owned by someone else
    other_ws = Workspace(name="other", owner_id="other-user")
    db_session.add(other_ws)
    await db_session.commit()
    await db_session.refresh(other_ws)

    response = await client.post(
        f"/upload?workspace_id={other_ws.id}",
        files=_pdf_file(),
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_upload_creates_document_record(client, mock_user, db_session):
    ws = await _make_workspace(db_session, mock_user)

    with patch("celery_app.ingest_doc_task") as mock_task:
        mock_task.delay = MagicMock()
        response = await client.post(
            f"/upload?workspace_id={ws.id}&vertical=lead_intel",
            files=_pdf_file(),
        )

    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "pending"
    assert data["vertical"] == "lead_intel"
    assert "doc_id" in data

    from uuid import UUID
    doc = await db_session.get(Document, UUID(data["doc_id"]))
    assert doc is not None
    assert doc.status == DocumentStatus.pending
    assert doc.workspace_id == ws.id
    assert doc.vertical == "lead_intel"


@pytest.mark.asyncio
async def test_upload_vertical_optional(client, mock_user, db_session):
    ws = await _make_workspace(db_session, mock_user)

    with patch("celery_app.ingest_doc_task") as mock_task:
        mock_task.delay = MagicMock()
        response = await client.post(
            f"/upload?workspace_id={ws.id}",
            files=_pdf_file(),
        )

    assert response.status_code == 201
    data = response.json()
    from uuid import UUID
    doc = await db_session.get(Document, UUID(data["doc_id"]))
    assert doc.vertical is None


# ── GET /upload/{doc_id} ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_doc_status_returns_correct_fields(client, mock_user, db_session):
    ws = await _make_workspace(db_session, mock_user)
    doc = Document(
        workspace_id=ws.id,
        uploaded_by=mock_user,
        filename="report.pdf",
        file_path="/tmp/report.pdf",
        file_size_bytes=1024,
        status=DocumentStatus.pending,
    )
    db_session.add(doc)
    await db_session.commit()
    await db_session.refresh(doc)

    response = await client.get(f"/upload/{doc.id}")
    assert response.status_code == 200
    data = response.json()
    assert data["doc_id"] == str(doc.id)
    assert data["filename"] == "report.pdf"
    assert data["status"] == "pending"
    assert "chunk_count" in data
    assert "error_message" in data


@pytest.mark.asyncio
async def test_get_doc_status_requires_membership(client, auth_as, db_session):
    owner = "owner@example.com"
    ws = Workspace(name="private", owner_id=owner)
    db_session.add(ws)
    await db_session.commit()
    await db_session.refresh(ws)

    doc = Document(
        workspace_id=ws.id,
        uploaded_by=owner,
        filename="secret.pdf",
        file_path="/tmp/secret.pdf",
        file_size_bytes=512,
    )
    db_session.add(doc)
    await db_session.commit()
    await db_session.refresh(doc)

    auth_as("intruder@example.com")
    response = await client.get(f"/upload/{doc.id}")
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_get_doc_status_404_for_unknown(client, mock_user):
    response = await client.get(f"/upload/{uuid4()}")
    assert response.status_code == 404


# ── pdf_service ───────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_parse_pdf_docling_returns_chunks():
    mock_result = MagicMock()
    mock_result.document.export_to_markdown.return_value = "# Title\n\nSome content about research."

    with patch("services.pdf_service._parse_with_docling") as mock_docling:
        mock_docling.return_value = [
            {"text": "chunk1", "metadata": {"source": "test.pdf", "page": None}},
            {"text": "chunk2", "metadata": {"source": "test.pdf", "page": None}},
        ]
        from services.pdf_service import parse_pdf
        chunks = await parse_pdf("/tmp/test.pdf")

    assert len(chunks) == 2
    assert chunks[0]["text"] == "chunk1"
    assert chunks[0]["metadata"]["source"] == "test.pdf"


@pytest.mark.asyncio
async def test_parse_pdf_falls_back_to_llamaparse():
    with patch("services.pdf_service._parse_with_docling", side_effect=RuntimeError("docling unavailable")), \
         patch("services.pdf_service._parse_with_llamaparse", new_callable=AsyncMock) as mock_llama, \
         patch("services.pdf_service.settings") as mock_settings:
        mock_settings.LLAMA_CLOUD_API_KEY = "test-key"
        mock_llama.return_value = [{"text": "llama chunk", "metadata": {"source": "f.pdf", "page": 1}}]

        from services.pdf_service import parse_pdf
        chunks = await parse_pdf("/tmp/test.pdf")

    mock_llama.assert_called_once()
    assert chunks[0]["text"] == "llama chunk"


@pytest.mark.asyncio
async def test_parse_pdf_returns_empty_when_both_fail():
    with patch("services.pdf_service._parse_with_docling", side_effect=RuntimeError("fail")), \
         patch("services.pdf_service._parse_with_llamaparse", new_callable=AsyncMock, side_effect=RuntimeError("fail")), \
         patch("services.pdf_service.settings") as mock_settings:
        mock_settings.LLAMA_CLOUD_API_KEY = "test-key"

        from services.pdf_service import parse_pdf
        chunks = await parse_pdf("/tmp/test.pdf")

    assert chunks == []


# ── ingest_service ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_ingest_doc_sets_ready(db_session):
    ws = Workspace(name="ingest-ws", owner_id="user1")
    db_session.add(ws)
    await db_session.commit()
    await db_session.refresh(ws)

    doc = Document(
        workspace_id=ws.id,
        uploaded_by="user1",
        filename="test.pdf",
        file_path="/tmp/test.pdf",
        file_size_bytes=100,
    )
    db_session.add(doc)
    await db_session.commit()
    await db_session.refresh(doc)

    mock_chunks = [
        {"text": f"chunk {i}", "metadata": {"source": "test.pdf", "page": None}}
        for i in range(3)
    ]

    with patch("services.ingest_service.AsyncSessionLocal") as mock_session_cls, \
         patch("services.ingest_service.parse_pdf", new_callable=AsyncMock, return_value=mock_chunks), \
         patch("services.ingest_service.ingest_documents") as mock_ingest:

        mock_ctx = AsyncMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=db_session)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)
        mock_session_cls.return_value = mock_ctx

        from services.ingest_service import ingest_doc
        await ingest_doc(doc.id)

    await db_session.refresh(doc)
    assert doc.status == DocumentStatus.ready
    assert doc.chunk_count == 3
    mock_ingest.assert_called_once_with(
        mock_chunks,
        collection_name=f"workspace_{ws.id}",
        vertical=None,
    )


@pytest.mark.asyncio
async def test_ingest_doc_passes_vertical(db_session):
    ws = Workspace(name="ingest-ws-v", owner_id="user3")
    db_session.add(ws)
    await db_session.commit()
    await db_session.refresh(ws)

    doc = Document(
        workspace_id=ws.id,
        uploaded_by="user3",
        filename="lead.pdf",
        file_path="/tmp/lead.pdf",
        file_size_bytes=200,
        vertical="lead_intel",
    )
    db_session.add(doc)
    await db_session.commit()
    await db_session.refresh(doc)

    mock_chunks = [{"text": "chunk", "metadata": {"source": "lead.pdf", "page": None}}]

    with patch("services.ingest_service.AsyncSessionLocal") as mock_session_cls, \
         patch("services.ingest_service.parse_pdf", new_callable=AsyncMock, return_value=mock_chunks), \
         patch("services.ingest_service.ingest_documents") as mock_ingest:

        mock_ctx = AsyncMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=db_session)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)
        mock_session_cls.return_value = mock_ctx

        from services.ingest_service import ingest_doc
        await ingest_doc(doc.id)

    mock_ingest.assert_called_once_with(
        mock_chunks,
        collection_name=f"workspace_{ws.id}",
        vertical="lead_intel",
    )


@pytest.mark.asyncio
async def test_ingest_doc_sets_failed_on_error(db_session):
    ws = Workspace(name="fail-ws", owner_id="user2")
    db_session.add(ws)
    await db_session.commit()
    await db_session.refresh(ws)

    doc = Document(
        workspace_id=ws.id,
        uploaded_by="user2",
        filename="bad.pdf",
        file_path="/tmp/bad.pdf",
        file_size_bytes=50,
    )
    db_session.add(doc)
    await db_session.commit()
    await db_session.refresh(doc)

    with patch("services.ingest_service.AsyncSessionLocal") as mock_session_cls, \
         patch("services.ingest_service.parse_pdf", new_callable=AsyncMock, side_effect=RuntimeError("parse error")):

        mock_ctx = AsyncMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=db_session)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)
        mock_session_cls.return_value = mock_ctx

        from services.ingest_service import ingest_doc
        await ingest_doc(doc.id)

    await db_session.refresh(doc)
    assert doc.status == DocumentStatus.failed
    assert "parse error" in (doc.error_message or "")
