import uuid
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from fastapi import HTTPException, status

from app.models.driver import Driver, VerificationStatus, DutyStatus, AvailabilityStatus
from app.utils.security import hash_password, verify_password, create_access_token


class DriverService:
    @staticmethod
    async def register_driver(
        db: AsyncSession,
        full_name: str,
        mobile_number: str,
        email: str,
        password: str,
        date_of_birth: Optional[str] = None,
        address: Optional[str] = None,
        emergency_contact: Optional[str] = None,
        driver_id_placeholder: Optional[str] = None,
        years_of_experience: int = 0,
    ) -> Driver:
        # Check duplicate mobile number
        stmt_mobile = select(Driver).where(Driver.mobile_number == mobile_number)
        res_mobile = await db.execute(stmt_mobile)
        if res_mobile.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Mobile number '{mobile_number}' is already registered."
            )

        # Check duplicate email
        stmt_email = select(Driver).where(Driver.email == email)
        res_email = await db.execute(stmt_email)
        if res_email.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Email address '{email}' is already registered."
            )

        driver_id = driver_id_placeholder.strip() if driver_id_placeholder and driver_id_placeholder.strip() else f"RR-DRV-{uuid.uuid4().hex[:6].upper()}"

        # Ensure driver_id uniqueness if placeholder was supplied
        stmt_id = select(Driver).where(Driver.id == driver_id)
        if (await db.execute(stmt_id)).scalar_one_or_none():
            driver_id = f"RR-DRV-{uuid.uuid4().hex[:6].upper()}"

        hashed_pwd = hash_password(password)

        driver = Driver(
            id=driver_id,
            full_name=full_name,
            mobile_number=mobile_number,
            email=email,
            hashed_password=hashed_pwd,
            date_of_birth=date_of_birth,
            residential_address=address,
            emergency_contact=emergency_contact,
            badge_id=driver_id_placeholder,
            years_of_experience=years_of_experience,
            verification_status=VerificationStatus.NOT_SUBMITTED.value,
            duty_status=DutyStatus.OFFLINE.value,
            availability_status=AvailabilityStatus.UNAVAILABLE.value,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

        db.add(driver)
        await db.commit()
        await db.refresh(driver)
        return driver

    @staticmethod
    async def login_driver(
        db: AsyncSession,
        mobile_number: str,
        password: str,
    ) -> tuple[Driver, str]:
        stmt = select(Driver).where(Driver.mobile_number == mobile_number)
        result = await db.execute(stmt)
        driver = result.scalar_one_or_none()

        if not driver or not verify_password(password, driver.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid mobile number or password."
            )

        # Generate JWT token
        token_data = {
            "sub": driver.id,
            "role": "DRIVER",
            "driver_id": driver.id,
            "mobile_number": driver.mobile_number,
        }
        token = create_access_token(data=token_data)
        return driver, token

    @staticmethod
    async def update_duty_status(
        db: AsyncSession,
        driver: Driver,
        new_duty_status: str,
    ) -> Driver:
        status_upper = new_duty_status.upper()
        if status_upper not in [DutyStatus.ONLINE.value, DutyStatus.OFFLINE.value]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid duty status. Allowed values: ONLINE, OFFLINE."
            )

        # CRITICAL BUSINESS RULE: Only VERIFIED drivers can go ONLINE
        if status_upper == DutyStatus.ONLINE.value:
            if driver.verification_status != VerificationStatus.VERIFIED.value:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Driver account is not verified. Current status: '{driver.verification_status}'. Only VERIFIED drivers can go ONLINE."
                )
            driver.duty_status = DutyStatus.ONLINE.value
            driver.availability_status = AvailabilityStatus.AVAILABLE.value
        else:
            driver.duty_status = DutyStatus.OFFLINE.value
            driver.availability_status = AvailabilityStatus.UNAVAILABLE.value

        driver.updated_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(driver)
        return driver

    @staticmethod
    async def update_availability_status(
        db: AsyncSession,
        driver: Driver,
        new_availability: str,
    ) -> Driver:
        avail_upper = new_availability.upper()
        if avail_upper not in [AvailabilityStatus.UNAVAILABLE.value, AvailabilityStatus.AVAILABLE.value, AvailabilityStatus.BUSY.value]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid availability status. Allowed values: UNAVAILABLE, AVAILABLE, BUSY."
            )

        if driver.duty_status == DutyStatus.OFFLINE.value:
            driver.availability_status = AvailabilityStatus.UNAVAILABLE.value
        else:
            if driver.verification_status != VerificationStatus.VERIFIED.value and avail_upper == AvailabilityStatus.AVAILABLE.value:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Unverified drivers cannot become dispatch eligible."
                )
            driver.availability_status = avail_upper

        driver.updated_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(driver)
        return driver
