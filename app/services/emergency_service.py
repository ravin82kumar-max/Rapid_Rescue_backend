import uuid
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from fastapi import HTTPException, status

from app.models.emergency import Emergency, EmergencyStatus


class EmergencyService:
    @staticmethod
    async def create_emergency(
        db: AsyncSession,
        patient_id: str,
        front_photo_path: str,
        rear_photo_path: str,
        latitude: float,
        longitude: float,
        accuracy: float,
        timestamp: Optional[datetime] = None,
        priority: Optional[str] = "CRITICAL",
        patient_name: Optional[str] = None,
        patient_phone: Optional[str] = None,
        pickup_address: Optional[str] = None,
        emergency_type: Optional[str] = "MEDICAL_EMERGENCY",
    ) -> Emergency:
        emergency = Emergency(
            patient_id=patient_id,
            front_photo_path=front_photo_path,
            rear_photo_path=rear_photo_path,
            latitude=latitude,
            longitude=longitude,
            accuracy=accuracy,
            timestamp=timestamp,
            priority=(priority or "CRITICAL").upper(),
            patient_name=patient_name,
            patient_phone=patient_phone,
            pickup_address=pickup_address,
            emergency_type=emergency_type or "MEDICAL_EMERGENCY",
            created_at=datetime.now(timezone.utc),
            status=EmergencyStatus.SEARCHING.value,
        )
        db.add(emergency)
        await db.commit()
        await db.refresh(emergency)
        return emergency

    @staticmethod
    async def get_emergency_by_id(
        db: AsyncSession, emergency_id_str: str
    ) -> Emergency:
        try:
            emergency_uuid = uuid.UUID(emergency_id_str)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid emergency ID format. Must be a valid UUID."
            )

        stmt = select(Emergency).where(Emergency.id == emergency_uuid)
        result = await db.execute(stmt)
        emergency = result.scalar_one_or_none()

        if not emergency:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Emergency with ID '{emergency_id_str}' not found."
            )

        return emergency

    @staticmethod
    async def cancel_emergency(
        db: AsyncSession, emergency_id_str: str
    ) -> Emergency:
        emergency = await EmergencyService.get_emergency_by_id(db, emergency_id_str)

        if emergency.status == EmergencyStatus.CANCELLED.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Emergency is already in CANCELLED status."
            )
        if emergency.status == EmergencyStatus.COMPLETED.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot cancel emergency in COMPLETED status."
            )

        emergency.status = EmergencyStatus.CANCELLED.value
        await db.commit()
        await db.refresh(emergency)
        return emergency
