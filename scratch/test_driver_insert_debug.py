import asyncio
import uuid
from datetime import datetime, timezone
from app.database.database import AsyncSessionLocal
from app.models.driver import Driver, VerificationStatus, DutyStatus, AvailabilityStatus

async def main():
    async with AsyncSessionLocal() as db:
        driver_id = f"DRV-RTRACK-{uuid.uuid4().hex[:8]}"
        unique_str = uuid.uuid4().hex[:8]
        driver = Driver(
            id=driver_id,
            full_name="John Driver",
            mobile_number=f"9{uuid.uuid4().int % 1000000000:09d}",
            email=f"driver_{unique_str}@example.com",
            hashed_password="hashed_pw",
            verification_status=VerificationStatus.VERIFIED.value,
            duty_status=DutyStatus.ONLINE.value,
            availability_status=AvailabilityStatus.AVAILABLE.value,
        )
        db.add(driver)
        try:
            await db.commit()
            print("SUCCESS! Driver inserted into database.")
        except Exception as e:
            print("ERROR INSERTING DRIVER:")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
