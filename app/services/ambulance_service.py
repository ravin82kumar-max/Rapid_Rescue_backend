from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from fastapi import HTTPException, status

from app.models.ambulance import Ambulance, AmbulanceType


class AmbulanceService:
    @staticmethod
    async def create_or_update_ambulance(
        db: AsyncSession,
        driver_id: str,
        registration_number: str,
        ambulance_type: str,
        equipment_capabilities: Optional[List[str]] = None,
        hospital_affiliation: Optional[str] = None,
    ) -> Ambulance:
        clean_reg = registration_number.strip().upper()

        # Check if registration_number is already used by another driver
        stmt_reg = select(Ambulance).where(Ambulance.registration_number == clean_reg)
        existing_reg = (await db.execute(stmt_reg)).scalar_one_or_none()

        if existing_reg and existing_reg.driver_id != driver_id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Ambulance with registration number '{clean_reg}' is already registered to another driver."
            )

        # Check if current driver already has an ambulance
        stmt_driver = select(Ambulance).where(Ambulance.driver_id == driver_id)
        driver_amb = (await db.execute(stmt_driver)).scalar_one_or_none()

        if driver_amb:
            driver_amb.registration_number = clean_reg
            driver_amb.ambulance_type = ambulance_type.upper()
            driver_amb.equipment_capabilities = equipment_capabilities or []
            driver_amb.hospital_affiliation = hospital_affiliation
            amb_record = driver_amb
        else:
            amb_record = Ambulance(
                driver_id=driver_id,
                registration_number=clean_reg,
                ambulance_type=ambulance_type.upper(),
                equipment_capabilities=equipment_capabilities or [],
                hospital_affiliation=hospital_affiliation,
            )
            db.add(amb_record)

        await db.commit()
        await db.refresh(amb_record)
        return amb_record

    @staticmethod
    async def get_driver_ambulance(
        db: AsyncSession,
        driver_id: str,
    ) -> Ambulance:
        stmt = select(Ambulance).where(Ambulance.driver_id == driver_id)
        ambulance = (await db.execute(stmt)).scalar_one_or_none()

        if not ambulance:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No ambulance registered for this driver."
            )

        return ambulance
