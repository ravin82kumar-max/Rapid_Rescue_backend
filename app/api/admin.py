from typing import Optional, List
from fastapi import APIRouter, Depends, Query, status, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.database import get_db
from app.utils.security import get_current_admin
from app.models.admin_user import AdminUser
from app.services.admin_service import AdminService
from app.schemas.admin import (
    AdminProfileSchema,
    AdminDashboardSummarySchema,
    AdminRejectVerificationSchema,
    AdminDriverListItemSchema,
    AdminDriverDetailSchema,
)

router = APIRouter(prefix="/api/v1/admin", tags=["Admin"])


@router.get("/me", response_model=AdminProfileSchema)
async def get_admin_profile(
    current_admin: AdminUser = Depends(get_current_admin),
):
    return AdminProfileSchema(
        adminId=current_admin.admin_id,
        fullName=current_admin.full_name,
        email=current_admin.email,
        mobileNumber=current_admin.mobile_number,
        role=current_admin.role or "ADMIN",
        isActive=current_admin.is_active,
    )


@router.get("/dashboard/summary")
async def get_dashboard_summary(
    current_admin: AdminUser = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    summary = await AdminService.get_dashboard_summary(db)
    return {
        "success": True,
        **summary,
    }


@router.get("/drivers/verification")
async def get_drivers_verification(
    status: Optional[str] = Query(None, alias="status", description="Filter by status (PENDING, UNDER_REVIEW, VERIFIED, REJECTED, NOT_SUBMITTED)"),
    verificationStatus: Optional[str] = Query(None, alias="verificationStatus"),
    current_admin: AdminUser = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    effective_status = status or verificationStatus
    drivers = await AdminService.get_drivers_verification_list(db, status_filter=effective_status)
    return {
        "success": True,
        "count": len(drivers),
        "drivers": drivers,
    }


@router.get("/drivers/{driver_id}/verification")
async def get_driver_verification_details(
    driver_id: str,
    current_admin: AdminUser = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    details = await AdminService.get_driver_verification_details(db, driver_id)
    return {
        "success": True,
        **details,
    }


@router.get("/drivers/{driver_id}/documents/{document_id}")
async def inspect_driver_document(
    driver_id: str,
    document_id: str,
    current_admin: AdminUser = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    local_path, mime_type, filename = await AdminService.get_driver_document_file(
        db=db,
        driver_id=driver_id,
        document_id=document_id,
    )
    return FileResponse(
        path=local_path,
        media_type=mime_type,
        filename=filename,
    )


@router.post("/drivers/{driver_id}/verification/start-review")
async def start_review(
    driver_id: str,
    current_admin: AdminUser = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    driver = await AdminService.start_review(db, driver_id, current_admin)
    return {
        "success": True,
        "message": f"Review started for driver '{driver_id}'",
        "driverId": driver.id,
        "verificationStatus": driver.verification_status,
    }


@router.post("/drivers/{driver_id}/verification/approve")
async def approve_verification(
    driver_id: str,
    current_admin: AdminUser = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    driver = await AdminService.approve_verification(db, driver_id, current_admin)
    return {
        "success": True,
        "message": f"Driver '{driver_id}' has been approved and verified.",
        "driverId": driver.id,
        "verificationStatus": driver.verification_status,
        "dutyStatus": driver.duty_status,
    }


@router.post("/drivers/{driver_id}/verification/reject")
async def reject_verification(
    driver_id: str,
    data: AdminRejectVerificationSchema,
    current_admin: AdminUser = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    driver = await AdminService.reject_verification(
        db=db,
        driver_id=driver_id,
        admin=current_admin,
        rejected_doc_type=data.rejectedDocumentType,
        rejection_reason=data.rejectionReason,
    )
    return {
        "success": True,
        "message": f"Verification rejected for driver '{driver_id}'.",
        "driverId": driver.id,
        "verificationStatus": driver.verification_status,
        "rejectedDocumentType": data.rejectedDocumentType,
        "rejectionReason": data.rejectionReason,
    }
