"""Add monitors table and Run.monitor_id

Foundation for continuous market-surveillance mode: a Monitor is a saved Run
template plus a cadence. Adds the `monitors` table and a nullable `monitor_id`
FK on `runs` linking each spawned run back to its monitor.

Revision ID: f1a2b3c4d5e6
Revises: a7b8c9d0e1f2
Create Date: 2026-07-12 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f1a2b3c4d5e6'
down_revision: Union[str, None] = 'a7b8c9d0e1f2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # `monitors` references runs.id (last_run_id) and workspaces.id — both
    # already exist, so this table is created first.
    op.create_table(
        'monitors',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('user_id', sa.String(length=255), nullable=False),
        sa.Column('workspace_id', sa.UUID(), nullable=True),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('topic', sa.Text(), nullable=False),
        sa.Column('format', sa.String(), nullable=False),
        sa.Column('vertical', sa.String(), nullable=True),
        sa.Column('vertical_inputs', sa.JSON(), server_default=sa.text("'{}'::json"), nullable=True),
        sa.Column('doc_paths', sa.JSON(), server_default=sa.text("'[]'::json"), nullable=True),
        sa.Column('interval_minutes', sa.Integer(), nullable=False),
        sa.Column('enabled', sa.Boolean(), server_default=sa.text('true'), nullable=False),
        sa.Column('next_run_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('last_run_id', sa.UUID(), nullable=True),
        sa.Column('last_run_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('notify_channel', sa.String(length=512), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id'], ),
        sa.ForeignKeyConstraint(['last_run_id'], ['runs.id'],
                                name='fk_monitors_last_run_id_runs'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_monitors_user_id'), 'monitors', ['user_id'], unique=False)
    op.create_index(op.f('ix_monitors_workspace_id'), 'monitors', ['workspace_id'], unique=False)
    op.create_index(op.f('ix_monitors_next_run_at'), 'monitors', ['next_run_at'], unique=False)

    # Now the reverse link on runs (monitors must exist first for this FK).
    op.add_column('runs', sa.Column('monitor_id', sa.UUID(), nullable=True))
    op.create_index(op.f('ix_runs_monitor_id'), 'runs', ['monitor_id'], unique=False)
    op.create_foreign_key(
        'fk_runs_monitor_id_monitors', 'runs', 'monitors', ['monitor_id'], ['id'],
    )


def downgrade() -> None:
    op.drop_constraint('fk_runs_monitor_id_monitors', 'runs', type_='foreignkey')
    op.drop_index(op.f('ix_runs_monitor_id'), table_name='runs')
    op.drop_column('runs', 'monitor_id')

    op.drop_index(op.f('ix_monitors_next_run_at'), table_name='monitors')
    op.drop_index(op.f('ix_monitors_workspace_id'), table_name='monitors')
    op.drop_index(op.f('ix_monitors_user_id'), table_name='monitors')
    op.drop_table('monitors')
