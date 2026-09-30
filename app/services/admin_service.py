import os
import uuid
from datetime import datetime, timezone
from typing import Optional, List, Tuple, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_
from fastapi import HTTPException, status

from app.models.admin_user import AdminUser
from app.models.admin_verification_action import AdminVerificationAction, VerificationActionEnum
from app.models.driver import Driver, VerificationStatus, DutyStatus
from app.models.driver_document import DriverDocument, DocumentType, DocumentCategory, DocumentStatus
from app.models.ambulance import Ambulance
from app.utils.security import verify_password, create_access_token

REQUIRED_DOCUMENTS_ORDER = [
    (DocumentType.DRIVING_LICENSE.value, DocumentCategory.DRIVER.value),
    (DocumentType.GOVERNMENT_ID.value, DocumentCategory.DRIVER.value),
    (DocumentType.DRIVER_SELFIE.value, DocumentCategory.DRIVER.value),
    (DocumentType.AMBULANCE_REGISTRATION.value, DocumentCategory.AMBULANCE.value),
    (DocumentType.AMBULANCE_PERMIT.value, DocumentCategory.AMBULANCE.value),
    (DocumentType.VEHICLE_INSURANCE.value, DocumentCategory.AMBULANCE.value),
]

ALL_REQUIRED_TYPES = {doc_type for doc_type, _ in REQUIRED_DOCUMENTS_ORDER}


class AdminService:
    @staticmethod
    async def create_default_admin_if_none(db: AsyncSession) -> Optional[AdminUser]:
        """Ensure at least one admin account exists in DB for testing/dev."""
        stmt = select(AdminUser).limit(1)
        existing = (await db.execute(stmt)).scalar_one_or_none()
        if existing:
            return existing

        from app.utils.security import hash_password
        admin = AdminUser(
            admin_id="ADM-1001",
            full_name="System Administrator",
            email="admin@rapidrescue.com",
            mobile_number="9999999999",
            password_hash=hash_password("AdminPassword123"),
            role="ADMIN",
            is_active=True,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        db.add(admin)
        await db.commit()
        await db.refresh(admin)
        return admin

    @staticmethod
    async def admin_login(
        db: AsyncSession,
        identifier: str,
        password: str,
    ) -> Tuple[AdminUser, str]:
        stmt = select(AdminUser).where(
            or_(
                AdminUser.email == identifier.strip(),
                AdminUser.mobile_number == identifier.strip(),
                AdminUser.admin_id == identifier.strip(),
            )
        )
        result = await db.execute(stmt)
        admin = result.scalar_one_or_none()

        if not admin or not verify_password(password, admin.password_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid admin email/mobile or password.",
            )

        if not admin.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin account is deactivated.",
            )

        token_data = {
            "sub": str(admin.id),
            "admin_id": admin.admin_id,
            "email": admin.email,
            "role": "ADMIN",
        }
        token = create_access_token(token_data)
        return admin, token

    @staticmethod
    async def get_dashboard_summary(db: AsyncSession) -> Dict[str, int]:
        pending_stmt = select(func.count(Driver.id)).where(Driver.verification_status == VerificationStatus.PENDING.value)
        under_review_stmt = select(func.count(Driver.id)).where(Driver.verification_status == VerificationStatus.UNDER_REVIEW.value)
        verified_stmt = select(func.count(Driver.id)).where(Driver.verification_status == VerificationStatus.VERIFIED.value)
        rejected_stmt = select(func.count(Driver.id)).where(Driver.verification_status == VerificationStatus.REJECTED.value)

        pending_count = (await db.execute(pending_stmt)).scalar() or 0
        under_review_count = (await db.execute(under_review_stmt)).scalar() or 0
        verified_count = (await db.execute(verified_stmt)).scalar() or 0
        rejected_count = (await db.execute(rejected_stmt)).scalar() or 0

        return {
            "pendingReview": pending_count,
            "underReview": under_review_count,
            "verifiedDrivers": verified_count,
            "rejectedDrivers": rejected_count,
        }

    @staticmethod
    async def get_drivers_verification_list(
        db: AsyncSession,
        status_filter: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        stmt = select(Driver)
        if status_filter:
            stmt = stmt.where(Driver.verification_status == status_filter.upper())
        else:
            # Default: show drivers requiring admin action (PENDING and UNDER_REVIEW)
            stmt = stmt.where(Driver.verification_status.in_([
                VerificationStatus.PENDING.value,
                VerificationStatus.UNDER_REVIEW.value,
            ]))

        stmt = stmt.order_by(Driver.updated_at.desc())
        drivers = (await db.execute(stmt)).scalars().all()

        results = []
        for driver in drivers:
            # Get uploaded docs
            doc_stmt = select(DriverDocument).where(DriverDocument.driver_id == driver.id)
            docs = (await db.execute(doc_stmt)).scalars().all()

            uploaded_req_types = {
                d.document_type for d in docs
                if d.document_type in ALL_REQUIRED_TYPES and d.status != DocumentStatus.REJECTED.value
            }
            doc_count = len(uploaded_req_types)

            latest_upload = max([d.uploaded_at for d in docs], default=driver.updated_at or driver.created_at)
            submitted_at_str = latest_upload.isoformat() if latest_upload else driver.created_at.isoformat()

            # Get attached ambulance
            amb_stmt = select(Ambulance).where(Ambulance.driver_id == driver.id)
            amb = (await db.execute(amb_stmt)).scalar_one_or_none()
            amb_info = None
            if amb:
                amb_info = {
                    "ambulanceId": amb.id,
                    "registrationNumber": amb.registration_number,
                    "ambulanceType": amb.ambulance_type,
                    "equipmentCapabilities": amb.equipment_capabilities,
                    "hospitalAffiliation": amb.hospital_affiliation,
                }

            results.append({
                "driverId": driver.id,
                "fullName": driver.full_name,
                "mobileNumber": driver.mobile_number,
                "email": driver.email,
                "dateOfBirth": driver.date_of_birth,
                "address": driver.residential_address,
                "emergencyContact": driver.emergency_contact,
                "yearsOfExperience": driver.years_of_experience,
                "verificationStatus": driver.verification_status,
                "submittedAt": submitted_at_str,
                "documentCount": doc_count,
                "requiredDocumentCount": 6,
                "dutyStatus": driver.duty_status,
                "availabilityStatus": driver.availability_status,
                "ambulance": amb_info,
            })

        return results

    @staticmethod
    async def get_driver_verification_details(
        db: AsyncSession,
        driver_id: str,
    ) -> Dict[str, Any]:
        stmt = select(Driver).where(Driver.id == driver_id)
        driver = (await db.execute(stmt)).scalar_one_or_none()

        if not driver:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Driver '{driver_id}' not found.",
            )

        doc_stmt = select(DriverDocument).where(DriverDocument.driver_id == driver_id)
        docs = (await db.execute(doc_stmt)).scalars().all()
        doc_map = {d.document_type: d for d in docs}

        formatted_docs = []
        valid_uploaded_req_types = set()

        for doc_type, category in REQUIRED_DOCUMENTS_ORDER:
            d = doc_map.get(doc_type)
            if d:
                if d.status != DocumentStatus.REJECTED.value:
                    valid_uploaded_req_types.add(doc_type)
                download_url = f"/api/v1/admin/drivers/{driver_id}/documents/{d.id}"
                formatted_docs.append({
                    "id": d.id,
                    "driverId": driver_id,
                    "documentType": d.document_type,
                    "category": d.category or category,
                    "originalFileName": d.file_name,
                    "fileName": d.file_name,
                    "mimeType": d.mime_type,
                    "fileSizeBytes": d.file_size_bytes,
                    "size": d.file_size_bytes,
                    "status": d.status,
                    "uploadedAt": d.uploaded_at.isoformat() if d.uploaded_at else None,
                    "uri": d.file_url,
                    "downloadUrl": download_url,
                    "rejectionReason": d.rejection_reason,
                })
            else:
                formatted_docs.append({
                    "id": None,
                    "driverId": driver_id,
                    "documentType": doc_type,
                    "category": category,
                    "originalFileName": "",
                    "fileName": "",
                    "mimeType": "",
                    "fileSizeBytes": 0,
                    "size": 0,
                    "status": DocumentStatus.NOT_UPLOADED.value,
                    "uploadedAt": None,
                    "uri": "",
                    "downloadUrl": "",
                    "rejectionReason": None,
                })

        # Ambulance info
        amb_stmt = select(Ambulance).where(Ambulance.driver_id == driver_id)
        amb = (await db.execute(amb_stmt)).scalar_one_or_none()
        amb_info = None
        if amb:
            amb_info = {
                "ambulanceId": amb.id,
                "registrationNumber": amb.registration_number,
                "ambulanceType": amb.ambulance_type,
                "equipmentCapabilities": amb.equipment_capabilities,
                "hospitalAffiliation": amb.hospital_affiliation,
            }

        latest_upload = max([d.uploaded_at for d in docs], default=driver.updated_at or driver.created_at)
        submitted_at_str = latest_upload.isoformat() if latest_upload else driver.created_at.isoformat()

        return {
            "driverId": driver.id,
            "fullName": driver.full_name,
            "mobileNumber": driver.mobile_number,
            "email": driver.email,
            "dateOfBirth": driver.date_of_birth,
            "dob": driver.date_of_birth,
            "address": driver.residential_address,
            "residentialAddress": driver.residential_address,
            "emergencyContact": driver.emergency_contact,
            "yearsOfExperience": driver.years_of_experience,
            "verificationStatus": driver.verification_status,
            "submittedAt": submitted_at_str,
            "dutyStatus": driver.duty_status,
            "availabilityStatus": driver.availability_status,
            "documentCount": len(valid_uploaded_req_types),
            "requiredDocumentCount": 6,
            "documents": formatted_docs,
            "ambulance": amb_info,
        }

    @staticmethod
    async def get_driver_document_file(
        db: AsyncSession,
        driver_id: str,
        document_id: str,
    ) -> Tuple[str, str, str]:
        """Returns tuple of (local_file_path, mime_type, file_name)."""
        stmt = select(DriverDocument).where(
            DriverDocument.id == document_id,
            DriverDocument.driver_id == driver_id,
        )
        doc = (await db.execute(stmt)).scalar_one_or_none()

        if not doc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Document '{document_id}' not found for driver '{driver_id}'.",
            )

        # file_url is like /uploads/driver_documents/xyz.pdf
        relative_path = doc.file_url.lstrip("/")
        if not os.path.exists(relative_path):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Physical file for document '{document_id}' not found on server.",
            )

        return relative_path, doc.mime_type, doc.file_name

    @staticmethod
    async def start_review(
        db: AsyncSession,
        driver_id: str,
        admin: AdminUser,
    ) -> Driver:
        stmt = select(Driver).where(Driver.id == driver_id)
        driver = (await db.execute(stmt)).scalar_one_or_none()

        if not driver:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Driver '{driver_id}' not found.",
            )

        if driver.verification_status != VerificationStatus.PENDING.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Driver verification status is '{driver.verification_status}'. Must be 'PENDING' to start review.",
            )

        prev_status = driver.verification_status
        new_status = VerificationStatus.UNDER_REVIEW.value
        driver.verification_status = new_status
        driver.updated_at = datetime.now(timezone.utc)

        action = AdminVerificationAction(
            driver_id=driver.id,
            admin_id=admin.id,
            action=VerificationActionEnum.START_REVIEW.value,
            previous_status=prev_status,
            new_status=new_status,
            created_at=datetime.now(timezone.utc),
        )
        db.add(action)

        await db.commit()
        await db.refresh(driver)
        return driver

    @staticmethod
    async def approve_verification(
        db: AsyncSession,
        driver_id: str,
        admin: AdminUser,
    ) -> Driver:
        stmt = select(Driver).where(Driver.id == driver_id)
        driver = (await db.execute(stmt)).scalar_one_or_none()

        if not driver:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Driver '{driver_id}' not found.",
            )

        if driver.verification_status != VerificationStatus.UNDER_REVIEW.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Driver verification status is '{driver.verification_status}'. Must be 'UNDER_REVIEW' to approve.",
            )

        # Check documents
        doc_stmt = select(DriverDocument).where(DriverDocument.driver_id == driver_id)
        docs = (await db.execute(doc_stmt)).scalars().all()

        uploaded_valid_types = {
            d.document_type for d in docs
            if d.document_type in ALL_REQUIRED_TYPES and d.status != DocumentStatus.REJECTED.value
        }

        missing = ALL_REQUIRED_TYPES - uploaded_valid_types
        if missing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot approve driver. Missing or rejected required documents: {sorted(list(missing))}",
            )

        prev_status = driver.verification_status
        new_status = VerificationStatus.VERIFIED.value
        driver.verification_status = new_status
        driver.updated_at = datetime.now(timezone.utc)
        # Note: dutyStatus remains OFFLINE unless driver explicitly changes it

        action = AdminVerificationAction(
            driver_id=driver.id,
            admin_id=admin.id,
            action=VerificationActionEnum.APPROVE.value,
            previous_status=prev_status,
            new_status=new_status,
            created_at=datetime.now(timezone.utc),
        )
        db.add(action)

        await db.commit()
        await db.refresh(driver)
        return driver

    @staticmethod
    async def reject_verification(
        db: AsyncSession,
        driver_id: str,
        admin: AdminUser,
        rejected_doc_type: Optional[str],
        rejection_reason: str,
    ) -> Driver:
        stmt = select(Driver).where(Driver.id == driver_id)
        driver = (await db.execute(stmt)).scalar_one_or_none()

        if not driver:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Driver '{driver_id}' not found.",
            )

        if driver.verification_status != VerificationStatus.UNDER_REVIEW.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Driver verification status is '{driver.verification_status}'. Must be 'UNDER_REVIEW' to reject.",
            )

        prev_status = driver.verification_status
        new_status = VerificationStatus.REJECTED.value
        driver.verification_status = new_status
        driver.updated_at = datetime.now(timezone.utc)

        if rejected_doc_type:
            doc_stmt = select(DriverDocument).where(
                DriverDocument.driver_id == driver_id,
                DriverDocument.document_type == rejected_doc_type.upper(),
            )
            doc = (await db.execute(doc_stmt)).scalar_one_or_none()
            if doc:
                doc.status = DocumentStatus.REJECTED.value
                doc.rejection_reason = rejection_reason
                doc.reviewed_at = datetime.now(timezone.utc)
                doc.reviewed_by = admin.full_name

        action = AdminVerificationAction(
            driver_id=driver.id,
            admin_id=admin.id,
            action=VerificationActionEnum.REJECT.value,
            previous_status=prev_status,
            new_status=new_status,
            rejection_reason=rejection_reason,
            rejected_document_type=rejected_doc_type.upper() if rejected_doc_type else None,
            created_at=datetime.now(timezone.utc),
        )
        db.add(action)

        await db.commit()
        await db.refresh(driver)
        return driver
