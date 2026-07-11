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


def _ws_dict(ws: Workspace) -> dict:
    return {"id": str(ws.id), "name": ws.name, "owner_id": ws.owner_id}


async def _create_workspace(db: AsyncSession, name: str, owner_id: str) -> Workspace:
    ws = Workspace(name=name, owner_id=owner_id)
    db.add(ws)
    await db.flush()  # populate ws.id before referencing it in WorkspaceMember
    db.add(WorkspaceMember(workspace_id=ws.id, user_id=owner_id, role="admin"))
    await db.commit()
    await db.refresh(ws)
    return ws


@router.post("", status_code=201)
async def create_workspace(
    body: CreateWorkspaceRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user),
):
    ws = await _create_workspace(db, body.name, user_id)
    return _ws_dict(ws)


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
    workspaces = result.scalars().all()
    # Every user needs at least one workspace for the UI to have an active tenant.
    if not workspaces:
        workspaces = [await _create_workspace(db, "Personal", user_id)]
    return [_ws_dict(ws) for ws in workspaces]


@router.get("/{workspace_id}/members")
async def list_members(
    workspace_id: UUID,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user),
):
    # Any member may see the roster; non-members get a 404 (don't reveal existence).
    caller = await db.get(WorkspaceMember, (workspace_id, user_id))
    if not caller:
        raise HTTPException(404, "Workspace not found")
    result = await db.execute(
        select(WorkspaceMember).where(WorkspaceMember.workspace_id == workspace_id)
    )
    return [{"user_id": m.user_id, "role": m.role} for m in result.scalars().all()]


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
    # Idempotent: re-adding an existing member updates their role instead of
    # crashing on the (workspace_id, user_id) primary key.
    member = await db.get(WorkspaceMember, (workspace_id, body.user_id))
    if member:
        member.role = body.role
    else:
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
    if member_user_id == ws.owner_id:
        raise HTTPException(400, "The workspace owner cannot be removed")
    member = await db.get(WorkspaceMember, (workspace_id, member_user_id))
    if member:
        await db.delete(member)
        await db.commit()
