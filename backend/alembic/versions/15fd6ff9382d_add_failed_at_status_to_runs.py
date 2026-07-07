"""add failed_at_status to runs

Revision ID: 15fd6ff9382d
Revises: d1e2f3a4b5c6
Create Date: 2026-07-08 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '15fd6ff9382d'
down_revision: Union[str, None] = 'd1e2f3a4b5c6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Reuses the existing `runstatus` Postgres enum type (create_type=False) —
# this column records the run's last active stage at the moment it failed,
# so failed runs can still show *where* they failed instead of going blank.
runstatus_enum = postgresql.ENUM(name='runstatus', create_type=False)


def upgrade() -> None:
    op.add_column('runs', sa.Column('failed_at_status', runstatus_enum, nullable=True))


def downgrade() -> None:
    op.drop_column('runs', 'failed_at_status')
