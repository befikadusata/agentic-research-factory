from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, PlainTextResponse
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from database import get_db
from models import Run, RunStatus
from services.pdf_service import markdown_to_pdf
from auth import get_current_user, assert_run_access
from starlette.background import BackgroundTask
import tempfile, os

router = APIRouter()


@router.get("/{run_id}/output/pdf")
async def download_pdf(
    run_id: UUID,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user),
):
    run = await db.get(Run, run_id)
    if not run or run.status != RunStatus.complete:
        raise HTTPException(404, "Output not available")
    await assert_run_access(run, user_id, db)
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
        path = f.name
    await markdown_to_pdf(run.final_output, path)
    return FileResponse(
        path,
        filename=f"report_{run_id}.pdf",
        media_type="application/pdf",
        background=BackgroundTask(os.remove, path),
    )


@router.get("/{run_id}/output/md")
async def download_md(
    run_id: UUID,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user),
):
    run = await db.get(Run, run_id)
    if not run or run.status != RunStatus.complete:
        raise HTTPException(404, "Output not available")
    await assert_run_access(run, user_id, db)
    return PlainTextResponse(
        run.final_output,
        headers={"Content-Disposition": f'attachment; filename="report_{run_id}.md"'},
    )
