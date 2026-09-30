from typing import Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_
from fastapi import HTTPException, status

from app.models.patient import Patient
from app.utils.security import hash_password, verify_password, create_access_token


class PatientService:
    @staticmethod
    async def register_patient(
        db: AsyncSession,
        full_name: str,
        mobile_number: str,
        password: str,
        email: Optional[str] = None,
        address: Optional[str] = None,
        blood_group: Optional[str] = None,
        emergency_contact_name: Optional[str] = None,
        emergency_contact_relationship: Optional[str] = None,
        emergency_contact_mobile: Optional[str] = None,
    ) -> Patient:
        # Check duplicate mobile number
        mobile_stmt = select(Patient).where(Patient.mobile_number == mobile_number.strip())
        existing_mobile = (await db.execute(mobile_stmt)).scalar_one_or_none()
        if existing_mobile:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Mobile number is already registered."
            )

        # Check duplicate email if provided
        clean_email = email.strip().lower() if email and email.strip() else None
        if clean_email:
            email_stmt = select(Patient).where(Patient.email == clean_email)
            existing_email = (await db.execute(email_stmt)).scalar_one_or_none()
            if existing_email:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Email address is already registered."
                )

        pwd_hash = hash_password(password)

        patient = Patient(
            full_name=full_name.strip(),
            mobile_number=mobile_number.strip(),
            email=clean_email,
            password_hash=pwd_hash,
            address=address.strip() if address else None,
            blood_group=blood_group.strip() if blood_group else None,
            emergency_contact_name=emergency_contact_name.strip() if emergency_contact_name else None,
            emergency_contact_relationship=emergency_contact_relationship.strip() if emergency_contact_relationship else None,
            emergency_contact_mobile=emergency_contact_mobile.strip() if emergency_contact_mobile else None,
        )

        db.add(patient)
        await db.commit()
        await db.refresh(patient)

        return patient

    @staticmethod
    async def login_patient(
        db: AsyncSession,
        identifier: str,
        password: str,
    ) -> Tuple[Patient, str]:
        clean_ident = identifier.strip()

        stmt = select(Patient).where(
            or_(
                Patient.mobile_number == clean_ident,
                Patient.email == clean_ident.lower()
            )
        )
        patient = (await db.execute(stmt)).scalar_one_or_none()

        if not patient:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid mobile number/email or password.",
                headers={"WWW-Authenticate": "Bearer"},
            )

        if not verify_password(password, patient.password_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid mobile number/email or password.",
                headers={"WWW-Authenticate": "Bearer"},
            )

        if not patient.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Patient account is deactivated.",
                headers={"WWW-Authenticate": "Bearer"},
            )

        token_payload = {
            "sub": str(patient.id),
            "patient_id": str(patient.id),
            "role": "PATIENT",
            "name": patient.full_name,
            "mobile": patient.mobile_number,
        }
        token = create_access_token(data=token_payload)

        return patient, token

    @staticmethod
    async def update_patient(
        db: AsyncSession,
        patient: Patient,
        full_name: Optional[str] = None,
        mobile_number: Optional[str] = None,
        email: Optional[str] = None,
        address: Optional[str] = None,
        blood_group: Optional[str] = None,
        emergency_contact_name: Optional[str] = None,
        emergency_contact_relationship: Optional[str] = None,
        emergency_contact_mobile: Optional[str] = None,
    ) -> Patient:
        if full_name is not None and full_name.strip():
            patient.full_name = full_name.strip()

        if mobile_number is not None and mobile_number.strip():
            clean_mob = mobile_number.strip()
            if clean_mob != patient.mobile_number:
                stmt = select(Patient).where(Patient.mobile_number == clean_mob)
                existing = (await db.execute(stmt)).scalar_one_or_none()
                if existing and existing.id != patient.id:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail="Mobile number is already registered by another user."
                    )
                patient.mobile_number = clean_mob

        if email is not None:
            clean_em = email.strip().lower() if email and email.strip() else None
            if clean_em != patient.email:
                if clean_em:
                    stmt = select(Patient).where(Patient.email == clean_em)
                    existing = (await db.execute(stmt)).scalar_one_or_none()
                    if existing and existing.id != patient.id:
                        raise HTTPException(
                            status_code=status.HTTP_409_CONFLICT,
                            detail="Email address is already registered by another user."
                        )
                patient.email = clean_em

        if address is not None:
            patient.address = address.strip() if address.strip() else None

        if blood_group is not None:
            patient.blood_group = blood_group.strip() if blood_group.strip() else None

        if emergency_contact_name is not None:
            patient.emergency_contact_name = emergency_contact_name.strip() if emergency_contact_name.strip() else None

        if emergency_contact_relationship is not None:
            patient.emergency_contact_relationship = emergency_contact_relationship.strip() if emergency_contact_relationship.strip() else None

        if emergency_contact_mobile is not None:
            patient.emergency_contact_mobile = emergency_contact_mobile.strip() if emergency_contact_mobile.strip() else None

        await db.commit()
        await db.refresh(patient)
        return patient
