import io
import threading
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from models import Document, DocumentStatus, Workspace, WorkspaceMember


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


@pytest.fixture
def stored_pdf(tmp_path):
    """A file that actually exists, for the ingest tests below.

    ingest_doc resolves file_path through storage_service before parsing, so a
    path pointing at nothing now fails as a missing object and never reaches the
    patched parse_pdf. These tests are about what happens *after* a successful
    fetch, so the bytes have to be there.
    """
    path = tmp_path / "stored.pdf"
    path.write_bytes(b"%PDF-1.7")
    return str(path)


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


def _fake_docling_document(pages_markdown: dict[int, str]):
    """A DoclingDocument stand-in whose per-page export mirrors `pages_markdown`."""
    document = MagicMock()
    document.pages = {page_no: MagicMock() for page_no in pages_markdown}

    def export(page_no=None, **kwargs):
        if page_no is None:
            return "\n\n".join(pages_markdown[p] for p in sorted(pages_markdown))
        return pages_markdown.get(page_no, "")

    document.export_to_markdown.side_effect = export
    result = MagicMock()
    result.document = document
    return result


def test_parse_with_docling_tags_each_chunk_with_its_page():
    """The primary parse path must carry each chunk's page number. Without it
    every internal citation renders 'Page: N/A' even though the citation
    pipeline and the Sources panel are fully built."""
    converted = _fake_docling_document({
        1: "# Intro\n\nFirst page body about the research question.",
        2: "## Method\n\nSecond page body describing the approach.",
    })

    with patch("services.pdf_service._build_converter") as build:
        build.return_value.convert.return_value = converted
        from services.pdf_service import _parse_with_docling
        chunks = _parse_with_docling("/tmp/paper.pdf")

    by_page = {c["metadata"]["page"] for c in chunks}
    assert by_page == {1, 2}
    assert all(c["metadata"]["source"] == "paper.pdf" for c in chunks)
    # Chunks must not straddle a page break, or the page number would be a lie.
    page_1_text = " ".join(c["text"] for c in chunks if c["metadata"]["page"] == 1)
    assert "Second page body" not in page_1_text


def test_parse_with_docling_skips_empty_pages():
    converted = _fake_docling_document({
        1: "Real content on the first page.",
        2: "   \n  ",
        3: "More content on the third page.",
    })

    with patch("services.pdf_service._build_converter") as build:
        build.return_value.convert.return_value = converted
        from services.pdf_service import _parse_with_docling
        chunks = _parse_with_docling("/tmp/gappy.pdf")

    assert {c["metadata"]["page"] for c in chunks} == {1, 3}


def test_parse_with_docling_falls_back_to_whole_document_without_pages():
    """Some inputs yield no page provenance. Ingesting without page numbers
    beats not ingesting at all, so this path stays open as the exception."""
    converted = _fake_docling_document({})
    converted.document.pages = {}
    converted.document.export_to_markdown.side_effect = None
    converted.document.export_to_markdown.return_value = "Flat document text with no pages."

    with patch("services.pdf_service._build_converter") as build:
        build.return_value.convert.return_value = converted
        from services.pdf_service import _parse_with_docling
        chunks = _parse_with_docling("/tmp/flat.pdf")

    assert len(chunks) == 1
    assert chunks[0]["metadata"]["page"] is None


def test_parse_with_docling_returns_empty_for_blank_document():
    converted = _fake_docling_document({})
    converted.document.pages = {}
    converted.document.export_to_markdown.side_effect = None
    converted.document.export_to_markdown.return_value = "   \n  "

    with patch("services.pdf_service._build_converter") as build:
        build.return_value.convert.return_value = converted
        from services.pdf_service import _parse_with_docling
        assert _parse_with_docling("/tmp/blank.pdf") == []


@pytest.mark.asyncio
async def test_ingest_doc_sets_ready(db_session, stored_pdf):
    ws = Workspace(name="ingest-ws", owner_id="user1")
    db_session.add(ws)
    await db_session.commit()
    await db_session.refresh(ws)

    doc = Document(
        workspace_id=ws.id,
        uploaded_by="user1",
        filename="test.pdf",
        file_path=stored_pdf,
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
async def test_ingest_doc_passes_vertical(db_session, stored_pdf):
    ws = Workspace(name="ingest-ws-v", owner_id="user3")
    db_session.add(ws)
    await db_session.commit()
    await db_session.refresh(ws)

    doc = Document(
        workspace_id=ws.id,
        uploaded_by="user3",
        filename="lead.pdf",
        file_path=stored_pdf,
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
async def test_ingest_doc_sets_failed_on_error(db_session, stored_pdf):
    ws = Workspace(name="fail-ws", owner_id="user2")
    db_session.add(ws)
    await db_session.commit()
    await db_session.refresh(ws)

    doc = Document(
        workspace_id=ws.id,
        uploaded_by="user2",
        filename="bad.pdf",
        file_path=stored_pdf,
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


@pytest.mark.asyncio
async def test_ingest_doc_marks_failed_when_no_chunks_extracted(db_session, stored_pdf):
    """parse_pdf swallows every parser failure and returns [], so an empty chunk
    list must not be recorded as `ready`. Marked ready with chunk_count=0, the UI
    reports a successful upload while nothing was embedded and every later run
    silently proceeds with no document context."""
    ws = Workspace(name="empty-ws", owner_id="user4")
    db_session.add(ws)
    await db_session.commit()
    await db_session.refresh(ws)

    doc = Document(
        workspace_id=ws.id,
        uploaded_by="user4",
        filename="scanned.pdf",
        file_path=stored_pdf,
        file_size_bytes=100,
    )
    db_session.add(doc)
    await db_session.commit()
    await db_session.refresh(doc)

    with patch("services.ingest_service.AsyncSessionLocal") as mock_session_cls, \
         patch("services.ingest_service.parse_pdf", new_callable=AsyncMock, return_value=[]), \
         patch("services.ingest_service.ingest_documents") as mock_ingest:

        mock_ctx = AsyncMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=db_session)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)
        mock_session_cls.return_value = mock_ctx

        from services.ingest_service import ingest_doc
        await ingest_doc(doc.id)

    await db_session.refresh(doc)
    assert doc.status == DocumentStatus.failed
    assert doc.chunk_count == 0
    assert doc.error_message
    # Nothing was embedded, so the vector store must not have been touched.
    mock_ingest.assert_not_called()


@pytest.mark.asyncio
async def test_ingest_doc_reports_missing_storage_distinctly(db_session, tmp_path):
    """A file the worker cannot fetch must not be reported as an unparseable PDF.

    This is the failure a container-local UPLOAD_DIR produced on every upload:
    the API wrote to its own filesystem, the worker's open() raised ENOENT,
    parse_pdf swallowed it and returned no chunks, and the operator was told
    their perfectly good PDF was empty or image-only. The message has to point
    at storage instead, and the parser must never be reached.
    """
    ws = Workspace(name="gone-ws", owner_id="user5")
    db_session.add(ws)
    await db_session.commit()
    await db_session.refresh(ws)

    doc = Document(
        workspace_id=ws.id,
        uploaded_by="user5",
        filename="vanished.pdf",
        file_path=str(tmp_path / "never-written.pdf"),
        file_size_bytes=100,
    )
    db_session.add(doc)
    await db_session.commit()
    await db_session.refresh(doc)

    with patch("services.ingest_service.AsyncSessionLocal") as mock_session_cls, \
         patch("services.ingest_service.parse_pdf", new_callable=AsyncMock) as mock_parse, \
         patch("services.ingest_service.ingest_documents") as mock_ingest:

        mock_ctx = AsyncMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=db_session)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)
        mock_session_cls.return_value = mock_ctx

        from services.ingest_service import ingest_doc
        await ingest_doc(doc.id)

    await db_session.refresh(doc)
    assert doc.status == DocumentStatus.failed
    assert "storage" in (doc.error_message or "")
    assert "no text" not in (doc.error_message or "").lower()
    mock_parse.assert_not_called()
    mock_ingest.assert_not_called()


@pytest.mark.asyncio
async def test_parse_pdf_timeout_abandons_the_parse_thread():
    """A docling parse that blows the timeout must not keep the caller (and, in
    production, the Celery worker child) waiting for it. The old
    run_in_executor(None, ...) submitted to the loop's default executor, whose
    threads asyncio.run() joins at teardown, so the guard fired but the task
    still hung for the parse's full duration."""
    import asyncio
    import time

    import services.pdf_service as pdf_service

    started = threading.Event()
    released = threading.Event()

    def _slow_parse(path):
        started.set()
        released.wait(30)      # far longer than the timeout below
        return [{"text": "too late", "metadata": {}}]

    with patch.object(pdf_service, "_parse_with_docling", _slow_parse), \
         patch.object(pdf_service, "PDF_PARSE_TIMEOUT_SEC", 0.2), \
         patch.object(pdf_service.settings, "LLAMA_CLOUD_API_KEY", None):
        began = time.monotonic()
        chunks = await asyncio.wait_for(pdf_service.parse_pdf("/tmp/slow.pdf"), timeout=5)
        elapsed = time.monotonic() - began

    assert chunks == []
    assert started.is_set()          # the parse really did start...
    assert elapsed < 3               # ...and we returned without waiting it out
    released.set()                   # let the orphan thread finish
