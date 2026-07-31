from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from uuid import UUID
from pydantic import BaseModel, Field
from database import get_db
from models import Workspace, WorkspaceMember
from auth import get_current_user, role_meets

router = APIRouter()


class CreateWorkspaceRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)


class AddMemberRequest(BaseModel):
    user_id: str
    role: str = Field(default="viewer", pattern="^(viewer|operator|admin)$")


def _ws_dict(ws: Workspace, role: str) -> dict:
    """Serialize a workspace along with the *calling* user's role in it.

    The role is per-caller, not a property of the workspace — it is what lets
    the UI gate operator-only actions (approving a HITL checkpoint) instead of
    showing the control to a viewer and surfacing the 403 as a failure.
    """
    return {"id": str(ws.id), "name": ws.name, "owner_id": ws.owner_id, "role": role}


async def _assert_may_manage_members(db: AsyncSession, workspace_id: UUID, user_id: str) -> Workspace:
    """Return the workspace if `user_id` may change its roster, else raise 403.

    Two ways in. The `admin` role is the intended one — it is the top rung of
    `_ROLE_RANK`, and gating this on ownership alone was what left that rung
    with nothing to do. Ownership is kept as a second, independent grant: it is
    the one claim that cannot be revoked, so a workspace whose admin rows were
    all deleted can still be repaired by the person who created it.

    A missing workspace raises the same 403 as an unauthorized one — a caller
    who may not manage this roster learns nothing about whether it exists.
    """
    denied = HTTPException(403, "Requires 'admin' role in this workspace")
    ws = await db.get(Workspace, workspace_id)
    if not ws:
        raise denied
    if ws.owner_id != user_id:
        member = await db.get(WorkspaceMember, (workspace_id, user_id))
        if not member or not role_meets(member.role, "admin"):
            raise denied
    return ws


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
    # _create_workspace always enrolls the creator as admin.
    return _ws_dict(ws, "admin")


@router.get("")
async def list_workspaces(
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user),
):
    result = await db.execute(
        select(Workspace, WorkspaceMember.role)
        .join(WorkspaceMember, WorkspaceMember.workspace_id == Workspace.id)
        .where(WorkspaceMember.user_id == user_id)
    )
    rows = result.all()
    # Every user needs at least one workspace for the UI to have an active tenant.
    if not rows:
        return [_ws_dict(await _create_workspace(db, "Personal", user_id), "admin")]
    return [_ws_dict(ws, role) for ws, role in rows]


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
    await _assert_may_manage_members(db, workspace_id, user_id)
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
    ws = await _assert_may_manage_members(db, workspace_id, user_id)
    # Ownership outranks the admin role here: an admin must not be able to evict
    # the owner and leave the workspace with no unrevokable claim on it.
    if member_user_id == ws.owner_id:
        raise HTTPException(400, "The workspace owner cannot be removed")
    member = await db.get(WorkspaceMember, (workspace_id, member_user_id))
    if member:
        await db.delete(member)
        await db.commit()
