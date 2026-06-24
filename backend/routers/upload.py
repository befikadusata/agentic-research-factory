from fastapi import APIRouter, UploadFile, File, HTTPException, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID, uuid4
import os
from database import get_db
from models import Document, DocumentStatus, WorkspaceMember
from auth import get_current_user

router = APIRouter()
UPLOAD_DIR = "/tmp/research_factory_uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

ALLOWED_TYPES = {"application/pdf"}
MAX_SIZE_MB = 20


@router.post("", status_code=201)
async def upload_file(
    file: UploadFile = File(...),
    workspace_id: UUID = Query(...),
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
    path = os.path.join(UPLOAD_DIR, f"{doc_id}.pdf")
    with open(path, "wb") as f:
        f.write(content)

    doc = Document(
        id=doc_id,
        workspace_id=workspace_id,
        uploaded_by=user_id,
        filename=file.filename,
        file_path=path,
        file_size_bytes=len(content),
    )
    db.add(doc)
    await db.commit()

    from celery_app import ingest_doc_task
    ingest_doc_task.delay(str(doc_id))

    return {"doc_id": str(doc_id), "filename": file.filename, "status": "pending"}


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
        "chunk_count": doc.chunk_count,
        "error_message": doc.error_message,
    }
