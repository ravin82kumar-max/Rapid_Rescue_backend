from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.database import get_db
from app.models.driver import Driver
from app.utils.security import get_current_driver
from app.services.ambulance_service import AmbulanceService
from app.schemas.ambulance import AmbulanceCreateSchema, AmbulanceResponseSchema

router = APIRouter(prefix="/api/v1/ambulances", tags=["Ambulance"])


@router.post("", response_model=AmbulanceResponseSchema, status_code=status.HTTP_201_CREATED)
async def create_or_update_ambulance(
    data: AmbulanceCreateSchema,
    current_driver: Driver = Depends(get_current_driver),
    db: AsyncSession = Depends(get_db),
):
    ambulance = await AmbulanceService.create_or_update_ambulance(
        db=db,
        driver_id=current_driver.id,
        registration_number=data.registrationNumber,
        ambulance_type=data.ambulanceType,
        equipment_capabilities=data.equipmentCapabilities,
        hospital_affiliation=data.hospitalAffiliation,
    )

    return AmbulanceResponseSchema(
        id=ambulance.id,
        driverId=ambulance.driver_id,
        registrationNumber=ambulance.registration_number,
        ambulanceType=ambulance.ambulance_type,
        equipmentCapabilities=ambulance.equipment_capabilities,
        hospitalAffiliation=ambulance.hospital_affiliation,
    )


@router.get("/me", response_model=AmbulanceResponseSchema)
async def get_my_ambulance(
    current_driver: Driver = Depends(get_current_driver),
    db: AsyncSession = Depends(get_db),
):
    ambulance = await AmbulanceService.get_driver_ambulance(
        db=db,
        driver_id=current_driver.id,
    )

    return AmbulanceResponseSchema(
        id=ambulance.id,
        driverId=ambulance.driver_id,
        registrationNumber=ambulance.registration_number,
        ambulanceType=ambulance.ambulance_type,
        equipmentCapabilities=ambulance.equipment_capabilities,
        hospitalAffiliation=ambulance.hospital_affiliation,
    )
