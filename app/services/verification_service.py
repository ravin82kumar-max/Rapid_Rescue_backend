import os
import uuid
from datetime import datetime, timezone
from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from fastapi import UploadFile, HTTPException, status

from app.models.driver import Driver, VerificationStatus
from app.models.driver_document import DriverDocument, DocumentType, DocumentCategory, DocumentStatus

REQUIRED_DOCUMENT_TYPES = {
    DocumentType.DRIVING_LICENSE.value,
    DocumentType.GOVERNMENT_ID.value,
    DocumentType.DRIVER_SELFIE.value,
    DocumentType.AMBULANCE_REGISTRATION.value,
    DocumentType.AMBULANCE_PERMIT.value,
    DocumentType.VEHICLE_INSURANCE.value,
}

AMBULANCE_DOC_TYPES = {
    DocumentType.AMBULANCE_REGISTRATION.value,
    DocumentType.AMBULANCE_PERMIT.value,
    DocumentType.VEHICLE_INSURANCE.value,
}

ALLOWED_MIME_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
    "application/pdf",
}

SELFIE_MIME_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
}

MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB


class VerificationService:
    @staticmethod
    async def upload_document(
        db: AsyncSession,
        driver_id: str,
        document_type_str: str,
        file: UploadFile,
    ) -> DriverDocument:
        doc_type_upper = document_type_str.upper()
        if doc_type_upper not in REQUIRED_DOCUMENT_TYPES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid document_type '{document_type_str}'. Allowed document types: {sorted(list(REQUIRED_DOCUMENT_TYPES))}"
            )

        mime_type = file.content_type.lower() if file.content_type else ""
        if doc_type_upper == DocumentType.DRIVER_SELFIE.value:
            if mime_type not in SELFIE_MIME_TYPES:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"DRIVER_SELFIE must be an image (JPEG, PNG, WEBP)."
                )
        else:
            if mime_type not in ALLOWED_MIME_TYPES:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid MIME type '{mime_type}'. Allowed formats: JPEG, PNG, WEBP, PDF."
                )

        content = await file.read()
        file_size = len(content)
        if file_size > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File size exceeds maximum limit of 10MB."
            )
        if file_size == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Uploaded file is empty."
            )

        # Determine Category
        category = DocumentCategory.AMBULANCE.value if doc_type_upper in AMBULANCE_DOC_TYPES else DocumentCategory.DRIVER.value

        # Save file to disk
        upload_dir = os.path.join("uploads", "driver_documents")
        os.makedirs(upload_dir, exist_ok=True)

        original_ext = os.path.splitext(file.filename)[1].lower() if file.filename else ""
        if not original_ext:
            original_ext = ".pdf" if mime_type == "application/pdf" else ".jpg"

        safe_filename = f"{driver_id}_{doc_type_upper}_{uuid.uuid4().hex[:8]}{original_ext}"
        local_path = os.path.join(upload_dir, safe_filename)

        with open(local_path, "wb") as f:
            f.write(content)

        file_url = f"/uploads/driver_documents/{safe_filename}"

        # Check existing document record of same type for driver
        stmt = select(DriverDocument).where(
            DriverDocument.driver_id == driver_id,
            DriverDocument.document_type == doc_type_upper
        )
        existing_doc = (await db.execute(stmt)).scalar_one_or_none()

        if existing_doc:
            existing_doc.file_url = file_url
            existing_doc.file_name = file.filename or safe_filename
            existing_doc.mime_type = mime_type
            existing_doc.file_size_bytes = file_size
            existing_doc.status = DocumentStatus.UPLOADED.value
            existing_doc.rejection_reason = None
            existing_doc.uploaded_at = datetime.now(timezone.utc)
            doc_record = existing_doc
        else:
            doc_record = DriverDocument(
                driver_id=driver_id,
                document_type=doc_type_upper,
                category=category,
                file_url=file_url,
                file_name=file.filename or safe_filename,
                mime_type=mime_type,
                file_size_bytes=file_size,
                status=DocumentStatus.UPLOADED.value,
                uploaded_at=datetime.now(timezone.utc),
            )
            db.add(doc_record)

        await db.commit()
        await db.refresh(doc_record)
        return doc_record

    @staticmethod
    async def get_driver_documents(db: AsyncSession, driver_id: str) -> List[DriverDocument]:
        stmt = select(DriverDocument).where(DriverDocument.driver_id == driver_id)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def submit_verification(db: AsyncSession, driver: Driver) -> Driver:
        docs = await VerificationService.get_driver_documents(db, driver.id)
        uploaded_types = {d.document_type for d in docs if d.status != DocumentStatus.REJECTED.value}

        missing_types = REQUIRED_DOCUMENT_TYPES - uploaded_types
        if missing_types:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Verification submission incomplete. Missing required documents: {sorted(list(missing_types))}"
            )

        driver.verification_status = VerificationStatus.PENDING.value
        driver.updated_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(driver)
        return driver

    @staticmethod
    async def start_admin_review(db: AsyncSession, driver_id: str) -> Driver:
        stmt = select(Driver).where(Driver.id == driver_id)
        driver = (await db.execute(stmt)).scalar_one_or_none()
        if not driver:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Driver '{driver_id}' not found.")

        driver.verification_status = VerificationStatus.UNDER_REVIEW.value
        driver.updated_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(driver)
        return driver

    @staticmethod
    async def approve_verification(db: AsyncSession, driver_id: str) -> Driver:
        stmt = select(Driver).where(Driver.id == driver_id)
        driver = (await db.execute(stmt)).scalar_one_or_none()
        if not driver:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Driver '{driver_id}' not found.")

        driver.verification_status = VerificationStatus.VERIFIED.value
        driver.updated_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(driver)
        return driver

    @staticmethod
    async def reject_verification(
        db: AsyncSession,
        driver_id: str,
        rejected_doc_type: Optional[str],
        rejection_reason: str,
        reviewer_name: str = "Admin",
    ) -> Driver:
        stmt = select(Driver).where(Driver.id == driver_id)
        driver = (await db.execute(stmt)).scalar_one_or_none()
        if not driver:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Driver '{driver_id}' not found.")

        driver.verification_status = VerificationStatus.REJECTED.value
        driver.updated_at = datetime.now(timezone.utc)

        if rejected_doc_type:
            doc_stmt = select(DriverDocument).where(
                DriverDocument.driver_id == driver_id,
                DriverDocument.document_type == rejected_doc_type.upper()
            )
            doc = (await db.execute(doc_stmt)).scalar_one_or_none()
            if doc:
                doc.status = DocumentStatus.REJECTED.value
                doc.rejection_reason = rejection_reason
                doc.reviewed_at = datetime.now(timezone.utc)
                doc.reviewed_by = reviewer_name

        await db.commit()
        await db.refresh(driver)
        return driver
