"""server_default for run JSON columns and timestamps

Revision ID: e5f6a7b8c9d0
Revises: 15fd6ff9382d
Create Date: 2026-07-11 00:00:00.000000

These columns previously had only a Python-side ORM default and were nullable,
so any row inserted outside the ORM (raw SQL, data migration, bulk import) got
NULL — which makes GET /runs/{id} 500, because RunDetailResponse requires them
non-null. Adding a server_default closes that gap, and we backfill existing
NULLs so old rows deserialize too.

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'e5f6a7b8c9d0'
down_revision: Union[str, None] = '15fd6ff9382d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_JSON_DEFAULTS = {
    'vertical_inputs': "'{}'::json",
    'doc_paths':       "'[]'::json",
    'logs':            "'[]'::json",
    'metrics':         "'{}'::json",
}
_TS_COLS = ('created_at', 'updated_at')


def upgrade() -> None:
    for col, default in _JSON_DEFAULTS.items():
        op.execute(f"UPDATE runs SET {col} = {default} WHERE {col} IS NULL")
        op.alter_column('runs', col, server_default=sa.text(default))
    for col in _TS_COLS:
        op.execute(f"UPDATE runs SET {col} = now() WHERE {col} IS NULL")
        op.alter_column('runs', col, server_default=sa.text('now()'))


def downgrade() -> None:
    for col in (*_JSON_DEFAULTS, *_TS_COLS):
        op.alter_column('runs', col, server_default=None)
