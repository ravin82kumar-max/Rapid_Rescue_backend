from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.database import get_db
from app.services.driver_service import DriverService
from app.schemas.auth import (
    DriverRegisterSchema,
    DriverLoginSchema,
    LoginResponse,
    SessionData,
)

router = APIRouter(prefix="/api/v1/auth", tags=["Authentication"])


@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(
    data: DriverRegisterSchema,
    db: AsyncSession = Depends(get_db),
):
    driver = await DriverService.register_driver(
        db=db,
        full_name=data.fullName,
        mobile_number=data.mobileNumber,
        email=data.email,
        password=data.password,
        date_of_birth=data.dateOfBirth,
        address=data.address,
        emergency_contact=data.emergencyContact,
        driver_id_placeholder=data.driverIdPlaceholder,
        years_of_experience=data.yearsOfExperience or 0,
    )

    return {
        "success": True,
        "message": "Driver registered successfully",
        "driverId": driver.id,
        "verificationStatus": driver.verification_status,
        "dutyStatus": driver.duty_status,
        "availabilityStatus": driver.availability_status,
    }


@router.post("/login", response_model=LoginResponse)
async def login(
    data: DriverLoginSchema,
    db: AsyncSession = Depends(get_db),
):
    driver, token = await DriverService.login_driver(
        db=db,
        mobile_number=data.mobileNumber,
        password=data.password,
    )

    session_info = SessionData(
        userId=driver.id,
        role="DRIVER",
        driverId=driver.id,
        name=driver.full_name,
        displayName=driver.full_name,
        mobileNumber=driver.mobile_number,
        email=driver.email,
        yearsOfExperience=driver.years_of_experience,
        token=token,
        createdAt=driver.created_at.isoformat(),
        isMockSession=False,
    )

    return LoginResponse(
        success=True,
        session=session_info,
        message="Login successful",
    )
