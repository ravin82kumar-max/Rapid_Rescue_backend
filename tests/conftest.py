import pytest
import pytest_asyncio
from app.database.database import engine


@pytest_asyncio.fixture(autouse=True)
async def cleanup_db_engine():
    yield
    await engine.dispose()
