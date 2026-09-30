import uuid
import pytest
import httpx
from app.main import app


@pytest.mark.asyncio
async def test_patient_registration_and_login_flow():
    unique_suffix = str(uuid.uuid4())[:8]
    mobile_num = f"91{uuid.uuid4().int % 100000000:08d}"
    email_addr = f"patient_{unique_suffix}@example.com"

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        # 1. Register Patient Success
        reg_payload = {
            "fullName": "Test Patient One",
            "mobileNumber": mobile_num,
            "password": "Password123!",
            "email": email_addr,
            "address": "123 Test Street",
            "bloodGroup": "O+",
            "emergencyContactName": "Emergency Contact",
            "emergencyContactRelationship": "Sibling",
            "emergencyContactMobile": "9111133333",
        }
        res = await client.post("/api/v1/auth/patient/register", json=reg_payload)
        assert res.status_code == 201
        data = res.json()
        assert data["success"] is True
        assert "patientId" in data
        patient_id = data["patientId"]

        # 2. Duplicate Mobile -> 409 Conflict
        dup_mob = reg_payload.copy()
        dup_mob["email"] = f"other_{unique_suffix}@example.com"
        res = await client.post("/api/v1/auth/patient/register", json=dup_mob)
        assert res.status_code == 409
        assert "Mobile number is already registered" in res.json()["detail"]

        # 3. Duplicate Email -> 409 Conflict
        dup_email = reg_payload.copy()
        dup_email["mobileNumber"] = f"92{uuid.uuid4().int % 100000000:08d}"
        res = await client.post("/api/v1/auth/patient/register", json=dup_email)
        assert res.status_code == 409
        assert "Email address is already registered" in res.json()["detail"]

        # 4. Login using Mobile
        res = await client.post("/api/v1/auth/patient/login", json={
            "identifier": mobile_num,
            "password": "Password123!"
        })
        assert res.status_code == 200
        login_data = res.json()
        assert login_data["success"] is True
        assert login_data["patientId"] == patient_id
        assert login_data["role"] == "PATIENT"
        token = login_data["token"]
        assert token is not None

        # 5. Login using Email
        res = await client.post("/api/v1/auth/patient/login", json={
            "identifier": email_addr,
            "password": "Password123!"
        })
        assert res.status_code == 200
        assert res.json()["token"] is not None

        # 6. Wrong Password -> 401
        res = await client.post("/api/v1/auth/patient/login", json={
            "identifier": mobile_num,
            "password": "WrongPassword!"
        })
        assert res.status_code == 401

        # 7. Unknown Identifier -> 401
        res = await client.post("/api/v1/auth/patient/login", json={
            "identifier": "000000000000",
            "password": "Password123!"
        })
        assert res.status_code == 401

        # 8. GET /patients/me with valid JWT
        res = await client.get(
            "/api/v1/patients/me",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert res.status_code == 200
        profile = res.json()
        assert profile["id"] == patient_id
        assert profile["fullName"] == "Test Patient One"
        assert profile["mobileNumber"] == mobile_num
        assert profile["bloodGroup"] == "O+"

        # 9. GET /patients/me without JWT -> 401
        res = await client.get("/api/v1/patients/me")
        assert res.status_code == 401

        # 10. Patient cannot access Driver-only endpoint -> 401 or 403
        res = await client.get(
            "/api/v1/drivers/me",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert res.status_code in (401, 403)

        # 11. PATCH /patients/me update address & blood group
        patch_res = await client.patch(
            "/api/v1/patients/me",
            json={"address": "789 New Address", "bloodGroup": "AB+"},
            headers={"Authorization": f"Bearer {token}"}
        )
        assert patch_res.status_code == 200
        updated_profile = patch_res.json()
        assert updated_profile["address"] == "789 New Address"
        assert updated_profile["bloodGroup"] == "AB+"

        # 12. Create Emergency with Patient JWT -> derives patient from JWT
        front_img = ("front.jpg", b"\xFF\xD8\xFF\xE0dummy_front_bytes", "image/jpeg")
        rear_img = ("rear.jpg", b"\xFF\xD8\xFF\xE0dummy_rear_bytes", "image/jpeg")

        em_res = await client.post(
            "/api/v1/emergencies",
            data={
                "latitude": "12.9716",
                "longitude": "77.5946",
                "accuracy": "5.0",
                "priority": "HIGH",
            },
            files={"front_photo": front_img, "rear_photo": rear_img},
            headers={"Authorization": f"Bearer {token}"}
        )
        assert em_res.status_code == 201
        em_data = em_res.json()
        assert em_data["success"] is True
        emergency_id = em_data["emergency_id"]

        # 13. Verify Emergency status endpoint returns DB patient details
        status_res = await client.get(f"/api/v1/emergencies/{emergency_id}")
        assert status_res.status_code == 200
        detail = status_res.json()["data"]
        assert detail["patient_id"] == patient_id
        assert detail["patient_name"] == "Test Patient One"
        assert detail["patient_phone"] == mobile_num
        assert detail["pickup_address"] == "789 New Address"
