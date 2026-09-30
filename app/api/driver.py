from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.database import get_db
from app.models.driver import Driver, VerificationStatus
from app.utils.security import get_current_driver
from app.services.driver_service import DriverService
from app.schemas.driver import (
    DriverProfileResponse,
    DutyStatusUpdateSchema,
    DutyStatusResponse,
    AvailabilityUpdateSchema,
    AvailabilityResponse,
)

router = APIRouter(prefix="/api/v1/drivers", tags=["Driver"])


@router.get("/me", response_model=DriverProfileResponse)
async def get_driver_profile(
    current_driver: Driver = Depends(get_current_driver),
):
    is_verified = (current_driver.verification_status == VerificationStatus.VERIFIED.value)
    return DriverProfileResponse(
        id=current_driver.id,
        fullName=current_driver.full_name,
        mobileNumber=current_driver.mobile_number,
        email=current_driver.email,
        dateOfBirth=current_driver.date_of_birth,
        address=current_driver.residential_address,
        emergencyContact=current_driver.emergency_contact,
        yearsOfExperience=current_driver.years_of_experience,
        isVerified=is_verified,
        verificationStatus=current_driver.verification_status,
        dutyStatus=current_driver.duty_status,
        availability=current_driver.availability_status,
    )


@router.patch("/me/duty-status", response_model=DutyStatusResponse)
async def update_duty_status(
    data: DutyStatusUpdateSchema,
    current_driver: Driver = Depends(get_current_driver),
    db: AsyncSession = Depends(get_db),
):
    updated_driver = await DriverService.update_duty_status(
        db=db,
        driver=current_driver,
        new_duty_status=data.status,
    )

    return DutyStatusResponse(
        success=True,
        dutyStatus=updated_driver.duty_status,
        availabilityStatus=updated_driver.availability_status,
        message=f"Duty status updated to {updated_driver.duty_status}",
    )


@router.patch("/me/availability", response_model=AvailabilityResponse)
async def update_availability(
    data: AvailabilityUpdateSchema,
    current_driver: Driver = Depends(get_current_driver),
    db: AsyncSession = Depends(get_db),
):
    updated_driver = await DriverService.update_availability_status(
        db=db,
        driver=current_driver,
        new_availability=data.status,
    )

    return AvailabilityResponse(
        success=True,
        availabilityStatus=updated_driver.availability_status,
        message=f"Availability status updated to {updated_driver.availability_status}",
    )
