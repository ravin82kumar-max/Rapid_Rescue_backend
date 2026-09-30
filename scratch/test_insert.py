import asyncio
from app.database.database import AsyncSessionLocal
from app.models.emergency import Emergency
import traceback

async def run():
    async with AsyncSessionLocal() as session:
        try:
            e = Emergency(
                patient_id="TEST_INSERT_PATIENT",
                front_photo_path="/uploads/f.jpg",
                rear_photo_path="/uploads/r.jpg",
                latitude=12.9716,
                longitude=77.5946,
                accuracy=5.0,
            )
            session.add(e)
            await session.commit()
            print("Successfully inserted Emergency!", e.id)
        except Exception as ex:
            print("FAILED TO INSERT:")
            traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(run())
