import sys
import os
from pathlib import Path

# Fix Windows console encoding for print
sys.stdout.reconfigure(encoding='utf-8')

# Ensure backend root is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import asyncio
import io
import httpx
from app.main import app

async def run_tests():
    print("--- STARTING PATIENT EMERGENCY MODULE VERIFICATION ---")

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        # 1. Root & DB Health Checks
        res = await client.get("/")
        print("Root Check:", res.status_code, res.json())
        assert res.status_code == 200
        assert res.json()["success"] is True

        res = await client.get("/health/db")
        print("DB Health Check:", res.status_code, res.json())
        assert res.status_code == 200
        assert res.json()["success"] is True

        # 2. Validation Test: Invalid Latitude
        front_img = ("front.jpg", b"fake_jpg_data_front", "image/jpeg")
        rear_img = ("rear.png", b"fake_png_data_rear", "image/png")

        res = await client.post(
            "/api/v1/emergencies",
            data={
                "latitude": "100.0",  # Invalid > 90
                "longitude": "77.59",
                "accuracy": "5.0",
                "patient_id": "patient_123",
            },
            files={"front_photo": front_img, "rear_photo": rear_img},
        )
        print("Invalid Lat Check (400 expected):", res.status_code, res.json())
        assert res.status_code == 400

        # 3. Validation Test: Missing Patient Identifier
        res = await client.post(
            "/api/v1/emergencies",
            data={
                "latitude": "12.9716",
                "longitude": "77.5946",
                "accuracy": "5.0",
            },
            files={"front_photo": front_img, "rear_photo": rear_img},
        )
        print("Missing Identifier Check (400 expected):", res.status_code, res.json())
        assert res.status_code == 400

        # 4. Successful Create Emergency
        res = await client.post(
            "/api/v1/emergencies",
            data={
                "latitude": "12.9716",
                "longitude": "77.5946",
                "accuracy": "4.5",
                "timestamp": "2026-09-26T14:20:00Z",
                "device_id": "DEV-XYZ-9876",
            },
            files={
                "front_photo": ("front_veh.jpg", b"\xFF\xD8\xFF\xE0dummy_front", "image/jpeg"),
                "rear_photo": ("rear_veh.png", b"\x89PNG\r\n\x1a\ndummy_rear", "image/png"),
            },
        )
        print("Create Emergency Response:", res.status_code, res.json())
        assert res.status_code == 201
        data = res.json()
        assert data["success"] is True
        assert data["message"] == "Emergency created successfully"
        assert data["status"] == "SEARCHING"
        emergency_id = data["emergency_id"]
        assert emergency_id is not None

        # 5. Get Emergency Status & Details
        res = await client.get(f"/api/v1/emergencies/{emergency_id}")
        print("Get Emergency Response:", res.status_code, res.json())
        assert res.status_code == 200
        get_data = res.json()
        assert get_data["success"] is True
        assert get_data["emergency_id"] == emergency_id
        assert get_data["status"] == "SEARCHING"
        assert get_data["data"]["patient_id"] == "DEV-XYZ-9876"
        assert get_data["data"]["latitude"] == 12.9716
        assert get_data["data"]["longitude"] == 77.5946

        # Check uploaded files exist on disk
        front_path = get_data["data"]["front_photo_url"].lstrip("/")
        rear_path = get_data["data"]["rear_photo_url"].lstrip("/")
        assert os.path.exists(front_path), f"Front photo file not found at {front_path}"
        assert os.path.exists(rear_path), f"Rear photo file not found at {rear_path}"
        print(f"Verified files saved successfully on disk: {front_path}, {rear_path}")

        # 6. Static File Access Check
        res = await client.get(get_data["data"]["front_photo_url"])
        print("Static File Fetch Check:", res.status_code, len(res.content))
        assert res.status_code == 200

        # 7. Cancel Emergency
        res = await client.post(f"/api/v1/emergencies/{emergency_id}/cancel")
        print("Cancel Emergency Response:", res.status_code, res.json())
        assert res.status_code == 200
        cancel_data = res.json()
        assert cancel_data["success"] is True
        assert cancel_data["status"] == "CANCELLED"

        # 8. Get Status After Cancel
        res = await client.get(f"/api/v1/emergencies/{emergency_id}")
        assert res.json()["status"] == "CANCELLED"

        # 9. Cancel Already Cancelled Emergency (400 Expected)
        res = await client.post(f"/api/v1/emergencies/{emergency_id}/cancel")
        print("Double Cancel Check (400 expected):", res.status_code, res.json())
        assert res.status_code == 400

    print("\n--- ALL VERIFICATION TESTS PASSED SUCCESSFULLY! ---")

if __name__ == "__main__":
    asyncio.run(run_tests())
