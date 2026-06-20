"""add multi-stage hitl statuses

Revision ID: b0eb3249c97e
Revises: bb27d181d2df
Create Date: 2026-06-01 23:17:55.938734

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b0eb3249c97e'
down_revision: Union[str, None] = 'bb27d181d2df'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE runstatus ADD VALUE IF NOT EXISTS 'awaiting_research_approval'")
    op.execute("ALTER TYPE runstatus ADD VALUE IF NOT EXISTS 'analyzing'")
    op.execute("ALTER TYPE runstatus ADD VALUE IF NOT EXISTS 'awaiting_analysis_approval'")
    op.execute("ALTER TYPE runstatus ADD VALUE IF NOT EXISTS 'awaiting_final_approval'")


def downgrade() -> None:
    # Postgres doesn't easily support removing enum values without recreating the type.
    # We will leave them for now to avoid complexity in a demo-ready project.
    pass
