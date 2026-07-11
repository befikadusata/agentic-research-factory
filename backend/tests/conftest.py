import os
# Must be set before any project module (config/database/main) is imported so
# config.py redirects the DB to an isolated test database. Otherwise the
# drop_all/create_all below would wipe the running app's data.
os.environ["TESTING"] = "1"

import pytest
import asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.engine import make_url
from sqlalchemy.pool import NullPool
from main import app
from auth import get_current_user
from database import get_db, Base
from config import settings
import models


def _ensure_test_database() -> None:
    """Create the isolated test database if it doesn't exist yet.

    settings.DATABASE_URL has already been redirected to the `<db>_test` sibling
    by config.py (guarded so it can never equal the app DB). We connect to the
    `postgres` maintenance DB and CREATE DATABASE (which can't run inside a txn,
    hence the AUTOCOMMIT engine). Going through SQLAlchemy reuses the exact same
    asyncpg driver + credential handling as the app engine.
    """
    from sqlalchemy import text

    url = make_url(settings.DATABASE_URL)
    dbname = url.database
    assert dbname and dbname != "postgres", "refusing to init a non-test DB"
    maint_url = url.set(database="postgres")

    async def _run() -> None:
        eng = create_async_engine(maint_url, isolation_level="AUTOCOMMIT")
        try:
            async with eng.connect() as conn:
                exists = await conn.scalar(
                    text("select 1 from pg_database where datname = :n"), {"n": dbname}
                )
                if not exists:
                    await conn.execute(text(f'CREATE DATABASE "{dbname}"'))
        finally:
            await eng.dispose()

    asyncio.run(_run())


_ensure_test_database()

@pytest.fixture
async def engine():
    # Use NullPool to avoid connection pooling issues across loops in tests
    engine = create_async_engine(settings.DATABASE_URL, echo=False, poolclass=NullPool)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    
    yield engine
    await engine.dispose()

@pytest.fixture
async def db_session(engine):
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session

@pytest.fixture
async def client(db_session):
    # Override get_db to use the fixture's session
    async def _get_db_override():
        yield db_session
    
    app.dependency_overrides[get_db] = _get_db_override
    
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    
    app.dependency_overrides.clear()

@pytest.fixture
def mock_user():
    user_id = "test-user-123"
    def override():
        return user_id
    
    app.dependency_overrides[get_current_user] = override
    yield user_id
    app.dependency_overrides.clear()

@pytest.fixture
def auth_as():
    def _set(user_id: str):
        def override():
            return user_id
        app.dependency_overrides[get_current_user] = override
        return user_id

    yield _set
    app.dependency_overrides.clear()

@pytest.fixture
async def redis_pool():
    """Initialise the Redis singleton for tests that invoke service functions directly
    (i.e. tests that do not go through the FastAPI app/lifespan)."""
    from utils.redis_client import init_redis_pool
    init_redis_pool()
    yield
