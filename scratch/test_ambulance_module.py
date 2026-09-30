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
    print("   STARTING AMBULANCE MODULE END-TO-END VERIFICATION")
    print("==================================================")

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:

        # ----------------------------------------------------
        # 1. Register & Login Driver 1
        # ----------------------------------------------------
        print("\n--- 1. Register & Login Driver 1 ---")
        reg1 = await client.post("/api/v1/auth/register", json={
            "fullName": "Driver One",
            "mobileNumber": "9111111111",
            "email": "driver1@rapidrescue.com",
            "password": "Password@123",
            "confirmPassword": "Password@123"
        })
        assert reg1.status_code == 201

        login1 = await client.post("/api/v1/auth/login", json={
            "mobileNumber": "9111111111",
            "password": "Password@123"
        })
        assert login1.status_code == 200
        token1 = login1.json()["session"]["token"]
        headers1 = {"Authorization": f"Bearer {token1}"}

        # ----------------------------------------------------
        # 2. Register Ambulance for Driver 1
        # ----------------------------------------------------
        print("\n--- 2. Register Ambulance for Driver 1 ---")
        amb_payload1 = {
            "registrationNumber": "TN-38-AM-1001",
            "ambulanceType": "ALS",
            "equipmentCapabilities": ["OXYGEN", "VENTILATOR", "DEFIBRILLATOR"],
            "hospitalAffiliation": "City General Hospital"
        }
        res = await client.post("/api/v1/ambulances", headers=headers1, json=amb_payload1)
        print("Register Ambulance Response:", res.status_code, res.json())
        assert res.status_code == 201
        amb1_data = res.json()
        assert amb1_data["registrationNumber"] == "TN-38-AM-1001"
        assert amb1_data["ambulanceType"] == "ALS"
        assert amb1_data["equipmentCapabilities"] == ["OXYGEN", "VENTILATOR", "DEFIBRILLATOR"]
        assert amb1_data["hospitalAffiliation"] == "City General Hospital"
        ambulance_id1 = amb1_data["id"]

        # ----------------------------------------------------
        # 3. Get My Ambulance for Driver 1
        # ----------------------------------------------------
        print("\n--- 3. Get My Ambulance (Driver 1) ---")
        res = await client.get("/api/v1/ambulances/me", headers=headers1)
        print("Get My Ambulance Response:", res.status_code, res.json())
        assert res.status_code == 200
        assert res.json()["id"] == ambulance_id1
        assert res.json()["registrationNumber"] == "TN-38-AM-1001"

        # ----------------------------------------------------
        # 4. Update Ambulance for Driver 1
        # ----------------------------------------------------
        print("\n--- 4. Update Ambulance for Driver 1 ---")
        amb_payload1_update = {
            "registrationNumber": "TN-38-AM-1001",
            "ambulanceType": "ALS",
            "equipmentCapabilities": ["OXYGEN", "VENTILATOR", "DEFIBRILLATOR", "ECG"],
            "hospitalAffiliation": "Apollo Hospital"
        }
        res = await client.post("/api/v1/ambulances", headers=headers1, json=amb_payload1_update)
        print("Update Ambulance Response:", res.status_code, res.json())
        assert res.status_code == 201
        assert res.json()["id"] == ambulance_id1
        assert res.json()["hospitalAffiliation"] == "Apollo Hospital"
        assert "ECG" in res.json()["equipmentCapabilities"]

        # ----------------------------------------------------
        # 5. Register & Login Driver 2
        # ----------------------------------------------------
        print("\n--- 5. Register & Login Driver 2 ---")
        reg2 = await client.post("/api/v1/auth/register", json={
            "fullName": "Driver Two",
            "mobileNumber": "9222222222",
            "email": "driver2@rapidrescue.com",
            "password": "Password@123",
            "confirmPassword": "Password@123"
        })
        assert reg2.status_code == 201

        login2 = await client.post("/api/v1/auth/login", json={
            "mobileNumber": "9222222222",
            "password": "Password@123"
        })
        token2 = login2.json()["session"]["token"]
        headers2 = {"Authorization": f"Bearer {token2}"}

        # ----------------------------------------------------
        # 6. Test Duplicate Registration Number Prevention (Expected 409)
        # ----------------------------------------------------
        print("\n--- 6. Duplicate Registration Number Check (409 Expected) ---")
        dup_payload = {
            "registrationNumber": "TN-38-AM-1001",  # Same reg number as Driver 1!
            "ambulanceType": "BLS",
            "equipmentCapabilities": ["OXYGEN"]
        }
        res = await client.post("/api/v1/ambulances", headers=headers2, json=dup_payload)
        print("Duplicate Registration Response (409 Expected):", res.status_code, res.json())
        assert res.status_code == 409

        # ----------------------------------------------------
        # 7. Register Unique Ambulance for Driver 2
        # ----------------------------------------------------
        print("\n--- 7. Register Unique Ambulance for Driver 2 ---")
        amb_payload2 = {
            "registrationNumber": "TN-38-AM-2002",
            "ambulanceType": "BLS",
            "equipmentCapabilities": ["OXYGEN", "FIRST_AID"]
        }
        res = await client.post("/api/v1/ambulances", headers=headers2, json=amb_payload2)
        print("Driver 2 Ambulance Response:", res.status_code, res.json())
        assert res.status_code == 201
        assert res.json()["registrationNumber"] == "TN-38-AM-2002"

        # ----------------------------------------------------
        # 8. Unauthenticated Access Test (Expected 401)
        # ----------------------------------------------------
        print("\n--- 8. Unauthenticated Access Check (401 Expected) ---")
        res = await client.post("/api/v1/ambulances", json=amb_payload2)
        print("Unauthenticated POST Response (401 Expected):", res.status_code)
        assert res.status_code == 401

        res = await client.get("/api/v1/ambulances/me")
        print("Unauthenticated GET Response (401 Expected):", res.status_code)
        assert res.status_code == 401

        # ----------------------------------------------------
        # 9. Verify Patient & Health APIs
        # ----------------------------------------------------
        print("\n--- 9. Verify Patient & Health APIs ---")
        res = await client.get("/")
        assert res.status_code == 200 and res.json()["success"] is True

        res = await client.get("/health/db")
        assert res.status_code == 200 and res.json()["success"] is True

    print("\n==================================================")
    print("   ALL AMBULANCE VERIFICATION TESTS PASSED SUCCESSFULLY! ")
    print("==================================================")

if __name__ == "__main__":
    asyncio.run(run_tests())
