from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from uuid import UUID
from pydantic import BaseModel, Field
from database import get_db
from models import Workspace, WorkspaceMember
from auth import get_current_user

router = APIRouter()


class CreateWorkspaceRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)


class AddMemberRequest(BaseModel):
    user_id: str
    role: str = Field(default="viewer", pattern="^(viewer|operator|admin)$")


@router.post("", status_code=201)
async def create_workspace(
    body: CreateWorkspaceRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user),
):
    ws = Workspace(name=body.name, owner_id=user_id)
    db.add(ws)
    await db.flush()  # ensure ws.id is populated before referencing it in WorkspaceMember
    db.add(WorkspaceMember(workspace_id=ws.id, user_id=user_id, role="admin"))
    await db.commit()
    await db.refresh(ws)
    return {"id": str(ws.id), "name": ws.name, "owner_id": ws.owner_id}


@router.get("")
async def list_workspaces(
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user),
):
    result = await db.execute(
        select(Workspace)
        .join(WorkspaceMember, WorkspaceMember.workspace_id == Workspace.id)
        .where(WorkspaceMember.user_id == user_id)
    )
    return [{"id": str(ws.id), "name": ws.name, "owner_id": ws.owner_id}
            for ws in result.scalars().all()]


@router.post("/{workspace_id}/members", status_code=201)
async def add_member(
    workspace_id: UUID,
    body: AddMemberRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user),
):
    ws = await db.get(Workspace, workspace_id)
    if not ws or ws.owner_id != user_id:
        raise HTTPException(403, "Only the workspace owner can add members")
    member = WorkspaceMember(workspace_id=workspace_id, user_id=body.user_id, role=body.role)
    db.add(member)
    await db.commit()
    return {"workspace_id": str(workspace_id), "user_id": body.user_id, "role": body.role}


@router.delete("/{workspace_id}/members/{member_user_id}", status_code=204)
async def remove_member(
    workspace_id: UUID,
    member_user_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user),
):
    ws = await db.get(Workspace, workspace_id)
    if not ws or ws.owner_id != user_id:
        raise HTTPException(403, "Only the workspace owner can remove members")
    member = await db.get(WorkspaceMember, (workspace_id, member_user_id))
    if member:
        await db.delete(member)
        await db.commit()
