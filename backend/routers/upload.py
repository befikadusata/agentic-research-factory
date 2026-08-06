from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from auth import get_current_user
from database import get_db
from models import Document, WorkspaceMember
from services.storage_service import store_upload

router = APIRouter()

ALLOWED_TYPES = {"application/pdf"}
MAX_SIZE_MB = 20


@router.post("", status_code=201)
async def upload_file(
    file: UploadFile = File(...),
    workspace_id: UUID = Query(...),
    vertical: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user),
):
    member = await db.get(WorkspaceMember, (workspace_id, user_id))
    if not member:
        raise HTTPException(403, "Not a member of this workspace")
    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(400, "Only PDF files are accepted")
    content = await file.read()
    if len(content) > MAX_SIZE_MB * 1024 * 1024:
        raise HTTPException(400, f"File exceeds {MAX_SIZE_MB}MB limit")

    doc_id = uuid4()
    # Store the bytes BEFORE the row is committed. The reverse order can dispatch
    # an ingest task for an object that isn't written yet, and leaves a row
    # pointing at nothing if the write then fails.
    locator = await store_upload(doc_id, content)

    doc = Document(
        id=doc_id,
        workspace_id=workspace_id,
        uploaded_by=user_id,
        filename=file.filename,
        file_path=locator,
        file_size_bytes=len(content),
        vertical=vertical,
    )
    db.add(doc)
    await db.commit()

    from celery_app import ingest_doc_task
    ingest_doc_task.delay(str(doc_id))

    return {"doc_id": str(doc_id), "filename": file.filename, "status": "pending", "vertical": vertical}


@router.get("/{doc_id}")
async def get_doc_status(
    doc_id: UUID,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user),
):
    doc = await db.get(Document, doc_id)
    if not doc:
        raise HTTPException(404, "Document not found")
    member = await db.get(WorkspaceMember, (doc.workspace_id, user_id))
    if not member:
        raise HTTPException(403, "Not a member of this workspace")
    return {
        "doc_id": str(doc.id),
        "filename": doc.filename,
        "status": doc.status,
        "vertical": doc.vertical,
        "chunk_count": doc.chunk_count,
        "error_message": doc.error_message,
    }
