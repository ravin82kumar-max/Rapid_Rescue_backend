from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.database import get_db
from app.models.patient import Patient
from app.utils.security import get_current_patient
from app.services.patient_service import PatientService
from app.schemas.patient import (
    PatientProfileSchema,
    PatientUpdateSchema,
)

router = APIRouter(prefix="/api/v1/patients", tags=["Patients"])


@router.get("/me", response_model=PatientProfileSchema)
async def get_patient_profile(
    current_patient: Patient = Depends(get_current_patient),
):
    return PatientProfileSchema(
        id=str(current_patient.id),
        fullName=current_patient.full_name,
        mobileNumber=current_patient.mobile_number,
        email=current_patient.email,
        address=current_patient.address,
        bloodGroup=current_patient.blood_group,
        emergencyContactName=current_patient.emergency_contact_name,
        emergencyContactRelationship=current_patient.emergency_contact_relationship,
        emergencyContactMobile=current_patient.emergency_contact_mobile,
        createdAt=current_patient.created_at.isoformat(),
    )


@router.patch("/me", response_model=PatientProfileSchema)
async def update_patient_profile(
    data: PatientUpdateSchema,
    current_patient: Patient = Depends(get_current_patient),
    db: AsyncSession = Depends(get_db),
):
    updated_patient = await PatientService.update_patient(
        db=db,
        patient=current_patient,
        full_name=data.fullName,
        mobile_number=data.mobileNumber,
        email=data.email,
        address=data.address,
        blood_group=data.bloodGroup,
        emergency_contact_name=data.emergencyContactName,
        emergency_contact_relationship=data.emergencyContactRelationship,
        emergency_contact_mobile=data.emergencyContactMobile,
    )

    return PatientProfileSchema(
        id=str(updated_patient.id),
        fullName=updated_patient.full_name,
        mobileNumber=updated_patient.mobile_number,
        email=updated_patient.email,
        address=updated_patient.address,
        bloodGroup=updated_patient.blood_group,
        emergencyContactName=updated_patient.emergency_contact_name,
        emergencyContactRelationship=updated_patient.emergency_contact_relationship,
        emergencyContactMobile=updated_patient.emergency_contact_mobile,
        createdAt=updated_patient.created_at.isoformat(),
    )
