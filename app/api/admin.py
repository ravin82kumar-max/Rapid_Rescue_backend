from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.database import get_db
from app.services.verification_service import VerificationService
from app.schemas.verification import AdminRejectVerificationSchema

router = APIRouter(prefix="/api/v1/admin/drivers", tags=["Admin"])


@router.post("/{driver_id}/verification/start-review")
async def start_review(
    driver_id: str,
    db: AsyncSession = Depends(get_db),
):
    driver = await VerificationService.start_admin_review(db, driver_id)
    return {
        "success": True,
        "message": f"Review started for driver '{driver_id}'",
        "verificationStatus": driver.verification_status,
    }


@router.post("/{driver_id}/verification/approve")
async def approve_verification(
    driver_id: str,
    db: AsyncSession = Depends(get_db),
):
    driver = await VerificationService.approve_verification(db, driver_id)
    return {
        "success": True,
        "message": f"Driver '{driver_id}' has been approved and verified.",
        "verificationStatus": driver.verification_status,
    }


@router.post("/{driver_id}/verification/reject")
async def reject_verification(
    driver_id: str,
    data: AdminRejectVerificationSchema,
    db: AsyncSession = Depends(get_db),
):
    driver = await VerificationService.reject_verification(
        db=db,
        driver_id=driver_id,
        rejected_doc_type=data.rejectedDocumentType,
        rejection_reason=data.rejectionReason,
    )
    return {
        "success": True,
        "message": f"Verification rejected for driver '{driver_id}'.",
        "verificationStatus": driver.verification_status,
        "rejectedDocumentType": data.rejectedDocumentType,
        "rejectionReason": data.rejectionReason,
    }
