import sys
import os
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import asyncio
import httpx
from app.main import app

async def run_tests():
    print("==================================================")
    print("   STARTING END-TO-END RR DRIVER MODULE VERIFICATION")
    print("==================================================")

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:

        # ----------------------------------------------------
        # TEST 1: Register Driver
        # ----------------------------------------------------
        print("\n--- TEST 1: Register Driver ---")
        reg_payload = {
            "fullName": "Ravin Driver",
            "mobileNumber": "9876543299",
            "email": "ravin.driver@example.com",
            "dateOfBirth": "1995-05-15",
            "address": "Coimbatore, TN",
            "emergencyContact": "9876543200",
            "password": "Password@123",
            "confirmPassword": "Password@123",
            "driverIdPlaceholder": "BADGE-999",
            "yearsOfExperience": 5
        }
        res = await client.post("/api/v1/auth/register", json=reg_payload)
        print("Register Response:", res.status_code, res.json())
        assert res.status_code == 201
        reg_data = res.json()
        assert reg_data["success"] is True
        assert reg_data["verificationStatus"] == "NOT_SUBMITTED"
        assert reg_data["dutyStatus"] == "OFFLINE"
        assert reg_data["availabilityStatus"] == "UNAVAILABLE"
        driver_id = reg_data["driverId"]
        print(f"Driver registered with ID: {driver_id}")

        # ----------------------------------------------------
        # TEST 2: Login Driver
        # ----------------------------------------------------
        print("\n--- TEST 2: Login Driver ---")
        login_payload = {
            "mobileNumber": "9876543299",
            "password": "Password@123"
        }
        res = await client.post("/api/v1/auth/login", json=login_payload)
        print("Login Response:", res.status_code, res.json())
        assert res.status_code == 200
        login_data = res.json()
        assert login_data["success"] is True
        token = login_data["session"]["token"]
        assert login_data["session"]["role"] == "DRIVER"
        assert token is not None
        auth_headers = {"Authorization": f"Bearer {token}"}

        # ----------------------------------------------------
        # TEST 3: Get Profile
        # ----------------------------------------------------
        print("\n--- TEST 3: Get Profile ---")
        res = await client.get("/api/v1/drivers/me", headers=auth_headers)
        print("Profile Response:", res.status_code, res.json())
        assert res.status_code == 200
        profile = res.json()
        assert profile["id"] == driver_id
        assert profile["fullName"] == "Ravin Driver"
        assert profile["isVerified"] is False
        assert profile["verificationStatus"] == "NOT_SUBMITTED"

        # ----------------------------------------------------
        # TEST 4: Try ONLINE before verification (Expected 403)
        # ----------------------------------------------------
        print("\n--- TEST 4: Try ONLINE before verification (403 Expected) ---")
        res = await client.patch("/api/v1/drivers/me/duty-status", headers=auth_headers, json={"status": "ONLINE"})
        print("ONLINE Response (403 Expected):", res.status_code, res.json())
        assert res.status_code == 403

        # ----------------------------------------------------
        # TEST 5: Upload all six required documents
        # ----------------------------------------------------
        print("\n--- TEST 5: Upload 6 Required Documents ---")
        doc_types = [
            "DRIVING_LICENSE",
            "GOVERNMENT_ID",
            "DRIVER_SELFIE",
            "AMBULANCE_REGISTRATION",
            "AMBULANCE_PERMIT",
            "VEHICLE_INSURANCE"
        ]

        for doc_type in doc_types:
            mime = "image/jpeg"
            dummy_content = b"\xFF\xD8\xFF\xE0dummy_doc_bytes"
            res = await client.post(
                "/api/v1/drivers/me/documents",
                headers=auth_headers,
                data={"document_type": doc_type},
                files={"file": (f"{doc_type}.jpg", dummy_content, mime)}
            )
            assert res.status_code == 201, f"Failed uploading {doc_type}: {res.text}"
            print(f"Uploaded {doc_type} -> ID: {res.json()['id']}")

        # ----------------------------------------------------
        # TEST 6: Submit Verification
        # ----------------------------------------------------
        print("\n--- TEST 6: Submit Verification ---")
        res = await client.post("/api/v1/drivers/me/verification/submit", headers=auth_headers)
        print("Submit Verification Response:", res.status_code, res.json())
        assert res.status_code == 200
        assert res.json()["verificationStatus"] == "PENDING"

        # ----------------------------------------------------
        # TEST 7: Admin Approve Verification
        # ----------------------------------------------------
        print("\n--- TEST 7: Admin Approve Verification ---")
        res = await client.post(f"/api/v1/admin/drivers/{driver_id}/verification/approve")
        print("Admin Approve Response:", res.status_code, res.json())
        assert res.status_code == 200
        assert res.json()["verificationStatus"] == "VERIFIED"

        # Check profile is verified
        res = await client.get("/api/v1/drivers/me", headers=auth_headers)
        assert res.json()["isVerified"] is True

        # ----------------------------------------------------
        # TEST 8: Driver Goes ONLINE
        # ----------------------------------------------------
        print("\n--- TEST 8: Driver Goes ONLINE ---")
        res = await client.patch("/api/v1/drivers/me/duty-status", headers=auth_headers, json={"status": "ONLINE"})
        print("Duty Status Response:", res.status_code, res.json())
        assert res.status_code == 200
        assert res.json()["dutyStatus"] == "ONLINE"
        assert res.json()["availabilityStatus"] == "AVAILABLE"

        # ----------------------------------------------------
        # TEST 9: Send GPS Location
        # ----------------------------------------------------
        print("\n--- TEST 9: Send GPS Location Telemetry ---")
        loc_payload = {
            "latitude": 11.0168,
            "longitude": 76.9558,
            "accuracy": 5.0,
            "altitude": 320.0,
            "heading": 90.0,
            "speed": 10.5,
            "timestamp": 1769486400000
        }
        res = await client.post("/api/v1/drivers/me/location", headers=auth_headers, json=loc_payload)
        print("Location Response:", res.status_code, res.json())
        assert res.status_code == 201
        assert res.json()["success"] is True

        # ----------------------------------------------------
        # TEST 10 & 11: Create Emergency & Test ACCEPT (Makes Driver BUSY)
        # ----------------------------------------------------
        print("\n--- TEST 10 & 11: Create Emergency & Test ACCEPT Dispatch ---")
        # 1. Create emergency from patient API
        front_img = ("front.jpg", b"\xFF\xD8\xFF\xE0dummy_front", "image/jpeg")
        rear_img = ("rear.png", b"\x89PNG\r\n\x1a\ndummy_rear", "image/png")
        emg_res = await client.post(
            "/api/v1/emergencies",
            data={
                "latitude": "11.0170",
                "longitude": "76.9560",
                "accuracy": "4.0",
                "patient_id": "PATIENT-DEV-100",
            },
            files={"front_photo": front_img, "rear_photo": rear_img}
        )
        assert emg_res.status_code == 201
        emergency_id = emg_res.json()["emergency_id"]
        print(f"Created Patient Emergency ID: {emergency_id}")

        # 2. Driver ACCEPTS emergency
        resp_payload = {
            "requestId": emergency_id,
            "action": "ACCEPT"
        }
        res = await client.post("/api/v1/dispatch/respond", headers=auth_headers, json=resp_payload)
        print("Accept Response:", res.status_code, res.json())
        assert res.status_code == 200
        assert res.json()["action"] == "ACCEPT"

        # Check driver profile is now BUSY
        res = await client.get("/api/v1/drivers/me", headers=auth_headers)
        print("Driver Availability after ACCEPT:", res.json()["availability"])
        assert res.json()["availability"] == "BUSY"

        # Test double ACCEPT (409 Conflict expected)
        res = await client.post("/api/v1/dispatch/respond", headers=auth_headers, json=resp_payload)
        print("Second Accept (409 Conflict expected):", res.status_code, res.json())
        assert res.status_code == 409

        # ----------------------------------------------------
        # TEST 12: COMPLETE Incident (Makes Driver AVAILABLE)
        # ----------------------------------------------------
        print("\n--- TEST 12: COMPLETE Incident ---")
        comp_payload = {"requestId": emergency_id}
        res = await client.post("/api/v1/dispatch/complete", headers=auth_headers, json=comp_payload)
        print("Complete Response:", res.status_code, res.json())
        assert res.status_code == 200
        assert res.json()["status"] == "COMPLETED"

        # Check driver profile is back to AVAILABLE
        res = await client.get("/api/v1/drivers/me", headers=auth_headers)
        print("Driver Availability after COMPLETE:", res.json()["availability"])
        assert res.json()["availability"] == "AVAILABLE"

        # ----------------------------------------------------
        # TEST 13: Verify Patient APIs still work intact
        # ----------------------------------------------------
        print("\n--- TEST 13: Verify Existing Patient APIs ---")
        res = await client.get("/")
        assert res.status_code == 200 and res.json()["success"] is True

        res = await client.get("/health/db")
        assert res.status_code == 200 and res.json()["success"] is True

        res = await client.get(f"/api/v1/emergencies/{emergency_id}")
        assert res.status_code == 200
        print("Patient GET Emergency Response:", res.json()["status"])
        assert res.json()["status"] == "COMPLETED"

        # Create another emergency & test patient cancellation
        emg2_res = await client.post(
            "/api/v1/emergencies",
            data={
                "latitude": "12.9716",
                "longitude": "77.5946",
                "accuracy": "3.0",
                "patient_id": "PATIENT-DEV-200",
            },
            files={"front_photo": front_img, "rear_photo": rear_img}
        )
        assert emg2_res.status_code == 201
        emergency2_id = emg2_res.json()["emergency_id"]

        cancel_res = await client.post(f"/api/v1/emergencies/{emergency2_id}/cancel")
        assert cancel_res.status_code == 200
        assert cancel_res.json()["status"] == "CANCELLED"
        print("Patient Cancel Emergency verified successfully!")

    print("\n==================================================")
    print("   ALL 13 VERIFICATION TESTS PASSED SUCCESSFULLY! ")
    print("==================================================")

if __name__ == "__main__":
    asyncio.run(run_tests())
