import os
import io
import pytest
import asyncio
from PIL import Image
from datetime import datetime, timezone
import httpx

from app.main import app
from app.services.eta_service import ETAService
from app.services.severity_service import SeverityService
from app.models.emergency import Emergency, EmergencyStatus
from app.models.driver import Driver, VerificationStatus, DutyStatus, AvailabilityStatus
from app.models.driver_location import DriverLocation
from app.models.ambulance import Ambulance
from app.services.dispatch_service import DispatchService
from app.services.emergency_service import EmergencyService
from app.database.database import AsyncSessionLocal, engine
from app.utils.security import create_access_token
from app.websocket.manager import manager as ws_manager


from sqlalchemy import update


def create_dummy_image_bytes() -> bytes:
    img = Image.new("RGB", (300, 300), color=(255, 100, 100))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


@pytest.mark.asyncio
async def test_full_realtime_tracking_bidirectional_flow():
    async with AsyncSessionLocal() as db:
            # 1. Register candidate driver and ambulance
            import uuid
            driver_id = f"DRV-RTRACK-{uuid.uuid4().hex[:8]}"
            unique_str = uuid.uuid4().hex[:8]
            driver = Driver(
                id=driver_id,
                full_name="John Driver",
                mobile_number=f"9{uuid.uuid4().int % 1000000000:09d}",
                email=f"driver_{unique_str}@example.com",


                hashed_password="hashed_pw",


                verification_status=VerificationStatus.VERIFIED.value,
                duty_status=DutyStatus.ONLINE.value,
                availability_status=AvailabilityStatus.AVAILABLE.value,
            )
            db.add(driver)
            await db.commit()

            ambulance_id = f"AMB-{os.urandom(4).hex()}"
            ambulance = Ambulance(
                id=ambulance_id,
                driver_id=driver_id,
                registration_number=f"KA-01-EQ-{os.urandom(2).hex().upper()}",
                ambulance_type="ALS",
            )
            db.add(ambulance)

            # 2. Driver Location Ping (placed virtually on top of pickup 12.9716, 77.5946 to be closest)
            loc = DriverLocation(
                driver_id=driver_id,
                latitude=12.9716001,
                longitude=77.5946001,
                accuracy_meters=5.0,
                recorded_at=datetime.now(timezone.utc),
            )
            db.add(loc)
            await db.commit()

            # 3. Create Emergency with full patient details
            img_bytes = create_dummy_image_bytes()
            files = {
                "front_photo": ("front.jpg", img_bytes, "image/jpeg"),
                "rear_photo": ("rear.jpg", img_bytes, "image/jpeg"),
            }
            data = {
                "latitude": "12.9716",
                "longitude": "77.5946",
                "accuracy": "5.0",
                "patient_id": "PATIENT_REALTIME_01",
                "patient_name": "Jane Doe",
                "patient_phone": "9876543210",
                "emergency_type": "CARDIAC_ARREST",
            }

            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
                res = await client.post("/api/v1/emergencies", files=files, data=data)

            assert res.status_code == 201
            res_json = res.json()
            emergency_id = res_json["emergency_id"]

            # Verify Emergency created in DB with patient details
            emergency = await EmergencyService.get_emergency_by_id(db, emergency_id)
            assert emergency.patient_name == "Jane Doe"
            assert emergency.patient_phone == "9876543210"
            assert emergency.emergency_type == "CARDIAC_ARREST"
            assert emergency.current_candidate_driver_id == driver_id

            # 4. Generate tokens for Driver & Patient authorization
            driver_token = create_access_token({"sub": driver_id, "driver_id": driver_id})
            patient_token = create_access_token({"sub": "PATIENT_REALTIME_01", "patient_id": "PATIENT_REALTIME_01"})
            unauthorized_driver_token = create_access_token({"sub": "DRV-UNAUTH", "driver_id": "DRV-UNAUTH"})

            # 5. Check Photo Authorization Endpoint
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
                # Driver offered/assigned photo access (Should Succeed 200)
                photo_res = await client.get(f"/api/v1/emergencies/{emergency_id}/photos/front?token={driver_token}")
                assert photo_res.status_code == 200
                assert photo_res.headers["content-type"] == "image/jpeg"

                # Unauthorized driver photo access (Should Fail 403)
                unauth_res = await client.get(f"/api/v1/emergencies/{emergency_id}/photos/front?token={unauthorized_driver_token}")
                assert unauth_res.status_code == 403

            # 6. Driver Accepts Emergency
            resp_record = await DispatchService.respond_to_dispatch(
                db=db,
                driver=driver,
                request_id_str=emergency_id,
                action_str="ACCEPT",
            )
            assert resp_record.action == "ACCEPT"

            # Verify Driver becomes BUSY and Emergency becomes ACCEPTED
            await db.refresh(driver)
            await db.refresh(emergency)
            assert driver.availability_status == AvailabilityStatus.BUSY.value
            assert emergency.status == EmergencyStatus.ACCEPTED.value
            assert emergency.assigned_driver_id == driver_id

            # 7. Test Concurrency / Second Driver Accept Attempt (Should Conflict 409)
            second_driver_id = f"DRV-SECOND-{os.urandom(4).hex()}"
            second_driver = Driver(
                id=second_driver_id,
                full_name="Second Driver",
                mobile_number=f"999{os.urandom(3).hex()[:7]}",
                email=f"second_{os.urandom(4).hex()}@example.com",
                hashed_password="pw",
                verification_status=VerificationStatus.VERIFIED.value,
                duty_status=DutyStatus.ONLINE.value,
                availability_status=AvailabilityStatus.AVAILABLE.value,
            )
            db.add(second_driver)
            await db.commit()

            from fastapi import HTTPException
            with pytest.raises(HTTPException) as exc_info:
                # Direct call using respond_to_dispatch raises HTTPException 409
                await DispatchService.respond_to_dispatch(
                    db=db,
                    driver=second_driver,
                    request_id_str=emergency_id,
                    action_str="ACCEPT",
                )
            assert exc_info.value.status_code == 409

            # 8. Driver sends Live Location Ping -> Triggers DRIVER_LOCATION_UPDATE & ETA_UPDATE
            headers = {"Authorization": f"Bearer {driver_token}"}
            loc_data = {
                "latitude": 12.9718,
                "longitude": 77.5948,
                "accuracy": 4.0,
                "speed": 10.0,
                "heading": 90.0,
            }
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
                loc_res = await client.post("/api/v1/drivers/me/location", json=loc_data, headers=headers)
            assert loc_res.status_code == 201

            # 9. Driver Completes Mission
            completed_emergency = await DispatchService.complete_incident(
                db=db,
                driver=driver,
                request_id_str=emergency_id,
            )
            assert completed_emergency.status == EmergencyStatus.COMPLETED.value

            # Verify Driver becomes AVAILABLE again
            await db.refresh(driver)
            assert driver.availability_status == AvailabilityStatus.AVAILABLE.value

