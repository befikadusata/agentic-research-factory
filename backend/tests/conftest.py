import pytest
import asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.pool import NullPool
from main import app
from auth import get_current_user
from database import get_db, Base
from config import settings
import models

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
