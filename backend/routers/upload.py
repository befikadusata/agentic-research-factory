from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
import os, uuid
from auth import get_current_user

router = APIRouter()
UPLOAD_DIR = "/tmp/research_factory_uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

ALLOWED_TYPES = {"application/pdf"}
MAX_SIZE_MB = 20

@router.post("")
async def upload_file(
    file: UploadFile = File(...),
    user_id: str = Depends(get_current_user),
):
    _ = user_id
    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(400, "Only PDF files are accepted")
    content = await file.read()
    if len(content) > MAX_SIZE_MB * 1024 * 1024:
        raise HTTPException(400, f"File exceeds {MAX_SIZE_MB}MB limit")
    doc_id = str(uuid.uuid4())
    path = os.path.join(UPLOAD_DIR, f"{doc_id}.pdf")
    with open(path, "wb") as f:
        f.write(content)
    return {"doc_id": doc_id, "filename": file.filename}
