from fastapi import APIRouter, Depends, File, Form, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.database import get_db
from app.models.driver import Driver
from app.utils.security import get_current_driver
from app.services.verification_service import VerificationService
from app.schemas.verification import (
    DocumentResponseSchema,
    VerificationStatusResponse,
)

router = APIRouter(prefix="/api/v1/drivers/me", tags=["Verification"])


@router.post("/documents", response_model=DocumentResponseSchema, status_code=status.HTTP_201_CREATED)
async def upload_document(
    document_type: str = Form(..., description="Document type identifier"),
    file: UploadFile = File(..., description="Document file upload (JPEG, PNG, WEBP, PDF)"),
    current_driver: Driver = Depends(get_current_driver),
    db: AsyncSession = Depends(get_db),
):
    doc = await VerificationService.upload_document(
        db=db,
        driver_id=current_driver.id,
        document_type_str=document_type,
        file=file,
    )

    return DocumentResponseSchema(
        id=doc.id,
        driverId=doc.driver_id,
        documentType=doc.document_type,
        category=doc.category,
        fileUrl=doc.file_url,
        fileName=doc.file_name,
        mimeType=doc.mime_type,
        fileSizeBytes=doc.file_size_bytes,
        status=doc.status,
        rejectionReason=doc.rejection_reason,
        uploadedAt=doc.uploaded_at,
    )


@router.post("/verification/submit")
async def submit_verification(
    current_driver: Driver = Depends(get_current_driver),
    db: AsyncSession = Depends(get_db),
):
    updated_driver = await VerificationService.submit_verification(db, current_driver)
    return {
        "success": True,
        "message": "Verification submitted successfully",
        "verificationStatus": updated_driver.verification_status,
    }


@router.get("/verification", response_model=VerificationStatusResponse)
async def get_verification_status(
    current_driver: Driver = Depends(get_current_driver),
    db: AsyncSession = Depends(get_db),
):
    docs = await VerificationService.get_driver_documents(db, current_driver.id)
    doc_schemas = [
        DocumentResponseSchema(
            id=d.id,
            driverId=d.driver_id,
            documentType=d.document_type,
            category=d.category,
            fileUrl=d.file_url,
            fileName=d.file_name,
            mimeType=d.mime_type,
            fileSizeBytes=d.file_size_bytes,
            status=d.status,
            rejectionReason=d.rejection_reason,
            uploadedAt=d.uploaded_at,
        )
        for d in docs
    ]

    return VerificationStatusResponse(
        verificationStatus=current_driver.verification_status,
        documents=doc_schemas,
    )
