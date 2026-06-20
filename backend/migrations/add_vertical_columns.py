"""
Migration: add vertical columns to runs table.

Run via: python -c "import asyncio; from migrations.add_vertical_columns import run_migration; asyncio.run(run_migration())"
Or: automatically applied via init_db() if using metadata.create_all.
"""
from sqlalchemy import text
from database import engine


async def run_migration():
    """Add vertical and vertical_inputs columns to the runs table (idempotent)."""
    async with engine.begin() as conn:
        await conn.execute(text(
            "ALTER TABLE runs ADD COLUMN IF NOT EXISTS vertical VARCHAR;"
        ))
        await conn.execute(text(
            "ALTER TABLE runs ADD COLUMN IF NOT EXISTS vertical_inputs JSONB DEFAULT '{}';"
        ))
    print("Migration complete: vertical columns added to runs table.")


if __name__ == "__main__":
    import asyncio
    asyncio.run(run_migration())
