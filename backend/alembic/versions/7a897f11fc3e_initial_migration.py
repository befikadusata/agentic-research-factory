"""Initial migration

Revision ID: 7a897f11fc3e
Revises:
Create Date: 2026-05-21 13:22:15.521194

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


# revision identifiers, used by Alembic.
revision: str = '7a897f11fc3e'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'workspaces',
        sa.Column('id', UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('owner_id', sa.String(length=255), nullable=False),
        sa.Column('settings', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_workspaces_owner_id', 'workspaces', ['owner_id'])

    op.create_table(
        'workspace_members',
        sa.Column('workspace_id', UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', sa.String(length=255), nullable=False),
        sa.Column('role', sa.String(length=50), nullable=False),
        sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id']),
        sa.PrimaryKeyConstraint('workspace_id', 'user_id'),
    )

    # awaiting_* / analyzing values are added later in b0eb3249c97e
    _runstatus = sa.Enum(
        'pending', 'researching', 'writing', 'complete', 'failed',
        name='runstatus',
    )

    op.create_table(
        'runs',
        sa.Column('id', UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('workspace_id', UUID(as_uuid=True), nullable=True),
        sa.Column('topic', sa.Text(), nullable=False),
        sa.Column('format', sa.String(), nullable=False),
        sa.Column('status', _runstatus, nullable=False),
        sa.Column('vertical', sa.String(), nullable=True),
        sa.Column('vertical_inputs', sa.JSON(), nullable=True),
        sa.Column('doc_paths', sa.JSON(), nullable=True),
        sa.Column('research_output', sa.Text(), nullable=True),
        sa.Column('final_output', sa.Text(), nullable=True),
        sa.Column('logs', sa.JSON(), nullable=True),
        sa.Column('metrics', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_runs_user_id', 'runs', ['user_id'])
    op.create_index('ix_runs_workspace_id', 'runs', ['workspace_id'])
    op.create_index('ix_runs_vertical', 'runs', ['vertical'])


def downgrade() -> None:
    op.drop_index('ix_runs_vertical', table_name='runs')
    op.drop_index('ix_runs_workspace_id', table_name='runs')
    op.drop_index('ix_runs_user_id', table_name='runs')
    op.drop_table('runs')
    sa.Enum(name='runstatus').drop(op.get_bind(), checkfirst=False)
    op.drop_table('workspace_members')
    op.drop_index('ix_workspaces_owner_id', table_name='workspaces')
    op.drop_table('workspaces')
