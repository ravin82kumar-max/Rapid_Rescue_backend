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


from app.services.patient_service import PatientService
from app.schemas.patient import (
    PatientRegisterSchema,
    PatientLoginSchema,
    PatientLoginResponse,
    PatientSessionData,
)


@router.post("/patient/register", status_code=status.HTTP_201_CREATED)
async def patient_register(
    data: PatientRegisterSchema,
    db: AsyncSession = Depends(get_db),
):
    patient = await PatientService.register_patient(
        db=db,
        full_name=data.fullName,
        mobile_number=data.mobileNumber,
        password=data.password,
        email=data.email,
        address=data.address,
        blood_group=data.bloodGroup,
        emergency_contact_name=data.emergencyContactName,
        emergency_contact_relationship=data.emergencyContactRelationship,
        emergency_contact_mobile=data.emergencyContactMobile,
    )

    return {
        "success": True,
        "message": "Patient registered successfully",
        "patientId": str(patient.id),
        "fullName": patient.full_name,
        "mobileNumber": patient.mobile_number,
        "email": patient.email,
        "createdAt": patient.created_at.isoformat(),
    }


@router.post("/patient/login", response_model=PatientLoginResponse)
async def patient_login(
    data: PatientLoginSchema,
    db: AsyncSession = Depends(get_db),
):
    patient, token = await PatientService.login_patient(
        db=db,
        identifier=data.identifier,
        password=data.password,
    )

    p_id = str(patient.id)
    c_at = patient.created_at.isoformat()

    session_info = PatientSessionData(
        userId=p_id,
        patientId=p_id,
        role="PATIENT",
        fullName=patient.full_name,
        mobileNumber=patient.mobile_number,
        email=patient.email,
        token=token,
        createdAt=c_at,
    )

    return PatientLoginResponse(
        success=True,
        message="Login successful",
        session=session_info,
        userId=p_id,
        patientId=p_id,
        role="PATIENT",
        fullName=patient.full_name,
        mobileNumber=patient.mobile_number,
        email=patient.email,
        token=token,
        createdAt=c_at,
    )

