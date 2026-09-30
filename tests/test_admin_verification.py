import os
import pytest
import io
import uuid
import httpx
from sqlalchemy import select

from app.main import app
from app.database.database import AsyncSessionLocal
from app.models.driver import Driver, VerificationStatus, DutyStatus
from app.models.driver_document import DriverDocument, DocumentType, DocumentStatus
from app.models.admin_user import AdminUser
from app.models.admin_verification_action import AdminVerificationAction, VerificationActionEnum
from app.utils.security import hash_password, create_access_token


async def get_or_create_admin():
    async with AsyncSessionLocal() as session:
        stmt = select(AdminUser).where(AdminUser.email == "testadmin@rapidrescue.com")
        existing = (await session.execute(stmt)).scalar_one_or_none()
        if existing:
            return existing

        admin = AdminUser(
            admin_id="ADM-TEST-100",
            full_name="Test Administrator",
            email="testadmin@rapidrescue.com",
            mobile_number="9876543299",
            password_hash=hash_password("AdminTestPass123"),
            role="ADMIN",
            is_active=True,
        )
        session.add(admin)
        await session.commit()
        await session.refresh(admin)
        return admin


async def get_or_create_driver(driver_id: str):
    async with AsyncSessionLocal() as session:
        stmt = select(Driver).where(Driver.id == driver_id)
        d = (await session.execute(stmt)).scalar_one_or_none()
        if not d:
            d = Driver(
                id=driver_id,
                full_name="Test Verification Driver",
                mobile_number=f"91{uuid.uuid4().int % 100000000:08d}",
                email=f"testverif_{uuid.uuid4().hex[:6]}@example.com",
                hashed_password=hash_password("DriverPass123"),
                date_of_birth="1992-04-10",
                residential_address="123 Test Street",
                emergency_contact="9123456781",
                years_of_experience=4,
                verification_status=VerificationStatus.NOT_SUBMITTED.value,
                duty_status=DutyStatus.OFFLINE.value,
            )
            session.add(d)
            await session.commit()
            await session.refresh(d)
        return d


@pytest.mark.asyncio
async def test_admin_login():
    await get_or_create_admin()
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        # Test valid login
        response = await client.post(
            "/api/v1/auth/admin/login",
            json={"identifier": "testadmin@rapidrescue.com", "password": "AdminTestPass123"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["role"] == "ADMIN"
        assert data["adminId"] == "ADM-TEST-100"
        assert "token" in data

        # Test invalid login
        bad_resp = await client.post(
            "/api/v1/auth/admin/login",
            json={"identifier": "testadmin@rapidrescue.com", "password": "WrongPassword"},
        )
        assert bad_resp.status_code == 401


@pytest.mark.asyncio
async def test_admin_profile():
    admin = await get_or_create_admin()
    admin_token = create_access_token({"sub": str(admin.id), "admin_id": admin.admin_id, "role": "ADMIN"})

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = await client.get("/api/v1/admin/me", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == "testadmin@rapidrescue.com"
        assert data["role"] == "ADMIN"


@pytest.mark.asyncio
async def test_admin_rbac_protection():
    driver_id = f"DRV-RBAC-{uuid.uuid4().hex[:6]}"
    await get_or_create_driver(driver_id)
    driver_token = create_access_token({"sub": driver_id, "driver_id": driver_id, "role": "DRIVER"})

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        headers = {"Authorization": f"Bearer {driver_token}"}
        response = await client.get("/api/v1/admin/me", headers=headers)
        assert response.status_code == 403

        summary_resp = await client.get("/api/v1/admin/dashboard/summary", headers=headers)
        assert summary_resp.status_code == 403


@pytest.mark.asyncio
async def test_admin_dashboard_summary():
    admin = await get_or_create_admin()
    admin_token = create_access_token({"sub": str(admin.id), "admin_id": admin.admin_id, "role": "ADMIN"})

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = await client.get("/api/v1/admin/dashboard/summary", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "pendingReview" in data
        assert "underReview" in data
        assert "verifiedDrivers" in data
        assert "rejectedDrivers" in data


@pytest.mark.asyncio
async def test_complete_driver_verification_workflow():
    admin = await get_or_create_admin()
    admin_token = create_access_token({"sub": str(admin.id), "admin_id": admin.admin_id, "role": "ADMIN"})

    driver_id = f"DRV-FLOW-{uuid.uuid4().hex[:6]}"
    await get_or_create_driver(driver_id)
    driver_token = create_access_token({"sub": driver_id, "driver_id": driver_id, "role": "DRIVER"})

    driver_headers = {"Authorization": f"Bearer {driver_token}"}
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        # Step 1: Upload all 6 required documents
        required_docs = [
            "DRIVING_LICENSE",
            "GOVERNMENT_ID",
            "DRIVER_SELFIE",
            "AMBULANCE_REGISTRATION",
            "AMBULANCE_PERMIT",
            "VEHICLE_INSURANCE",
        ]

        for doc_type in required_docs:
            file_content = b"%PDF-1.4 test document content"
            mime = "application/pdf" if doc_type != "DRIVER_SELFIE" else "image/jpeg"
            ext = ".pdf" if doc_type != "DRIVER_SELFIE" else ".jpg"
            if doc_type == "DRIVER_SELFIE":
                file_content = b"\xff\xd8\xff\xe0\x00\x10JFIF"

            files = {"file": (f"{doc_type.lower()}{ext}", io.BytesIO(file_content), mime)}
            up_resp = await client.post(
                "/api/v1/drivers/me/documents",
                headers=driver_headers,
                data={"document_type": doc_type},
                files=files,
            )
            assert up_resp.status_code in (200, 201), f"Upload failed for {doc_type}: {up_resp.text}"

        # Step 2: Submit verification
        sub_resp = await client.post("/api/v1/drivers/me/verification/submit", headers=driver_headers)
        assert sub_resp.status_code == 200
        assert sub_resp.json()["verificationStatus"] == "PENDING"

        # Step 3: Admin gets driver verification details
        dt_resp = await client.get(f"/api/v1/admin/drivers/{driver_id}/verification", headers=admin_headers)
        assert dt_resp.status_code == 200
        dt_data = dt_resp.json()
        assert dt_data["documentCount"] == 6
        assert len(dt_data["documents"]) == 6

        # Step 4: Admin starts review (PENDING -> UNDER_REVIEW)
        sr_resp = await client.post(f"/api/v1/admin/drivers/{driver_id}/verification/start-review", headers=admin_headers)
        assert sr_resp.status_code == 200
        assert sr_resp.json()["verificationStatus"] == "UNDER_REVIEW"

        # Step 5: Admin rejects driving license (UNDER_REVIEW -> REJECTED)
        rej_resp = await client.post(
            f"/api/v1/admin/drivers/{driver_id}/verification/reject",
            headers=admin_headers,
            json={
                "rejectedDocumentType": "DRIVING_LICENSE",
                "rejectionReason": "Image is blurry and unreadable",
            },
        )
        assert rej_resp.status_code == 200
        assert rej_resp.json()["verificationStatus"] == "REJECTED"
        assert rej_resp.json()["rejectedDocumentType"] == "DRIVING_LICENSE"

        # Step 6: Driver re-uploads driving license and resubmits (REJECTED -> PENDING)
        new_dl_content = b"\xff\xd8\xff\xe0\x00\x10JFIF clear selfie image"
        files = {"file": ("license_clear.jpg", io.BytesIO(new_dl_content), "image/jpeg")}
        up_fixed = await client.post(
            "/api/v1/drivers/me/documents",
            headers=driver_headers,
            data={"document_type": "DRIVING_LICENSE"},
            files=files,
        )
        assert up_fixed.status_code in (200, 201)

        resub_resp = await client.post("/api/v1/drivers/me/verification/submit", headers=driver_headers)
        assert resub_resp.status_code == 200
        assert resub_resp.json()["verificationStatus"] == "PENDING"

        # Step 7: Admin starts review again (PENDING -> UNDER_REVIEW)
        sr_resp2 = await client.post(f"/api/v1/admin/drivers/{driver_id}/verification/start-review", headers=admin_headers)
        assert sr_resp2.status_code == 200
        assert sr_resp2.json()["verificationStatus"] == "UNDER_REVIEW"

        # Step 8: Admin approves driver (UNDER_REVIEW -> VERIFIED)
        app_resp = await client.post(f"/api/v1/admin/drivers/{driver_id}/verification/approve", headers=admin_headers)
        assert app_resp.status_code == 200
        assert app_resp.json()["verificationStatus"] == "VERIFIED"
        assert app_resp.json()["dutyStatus"] == "OFFLINE"  # Duty status remains OFFLINE!

        # Step 9: Document inspection test
        first_doc_id = dt_data["documents"][0]["id"]
        if first_doc_id:
            doc_insp_resp = await client.get(
                f"/api/v1/admin/drivers/{driver_id}/documents/{first_doc_id}",
                headers=admin_headers,
            )
            assert doc_insp_resp.status_code == 200

    # Step 10: Verify audit actions created in database
    async with AsyncSessionLocal() as session:
        stmt = select(AdminVerificationAction).where(AdminVerificationAction.driver_id == driver_id).order_by(AdminVerificationAction.created_at)
        actions = (await session.execute(stmt)).scalars().all()
        assert len(actions) >= 4
        action_names = [a.action for a in actions]
        assert "START_REVIEW" in action_names
        assert "REJECT" in action_names
        assert "RESUBMIT" in action_names
        assert "APPROVE" in action_names
