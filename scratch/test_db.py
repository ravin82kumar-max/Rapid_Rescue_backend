import asyncio
from app.database.database import AsyncSessionLocal
from sqlalchemy import text

async def test_conn():
    try:
        async with AsyncSessionLocal() as session:
            res = await session.execute(text("SELECT 1"))
            print("DB connection OK:", res.scalar())
    except Exception as e:
        print("DB connection error:", e)

if __name__ == "__main__":
    asyncio.run(test_conn())
