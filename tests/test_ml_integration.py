import os
import io
import pytest
from PIL import Image
from datetime import datetime, timezone
import httpx

from app.main import app
from app.services.eta_service import ETAService
from app.services.severity_service import SeverityService
from app.models.emergency import Emergency, EmergencyStatus
from app.models.driver import Driver, VerificationStatus, DutyStatus, AvailabilityStatus
from app.models.driver_location import DriverLocation
from app.services.dispatch_service import DispatchService
from app.database.database import AsyncSessionLocal, engine


def create_dummy_image_bytes() -> bytes:
    img = Image.new("RGB", (300, 300), color=(255, 100, 100))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


# Test 1: ETA Model Loads Successfully
def test_eta_model_loads():
    loaded = ETAService.load_model()
    assert loaded is True
    assert ETAService.is_loaded() is True


# Test 2: ETA Prediction Works with Known Sample
def test_eta_prediction_known_sample():
    eta = ETAService.predict_eta(
        distance_km=5.2,
        traffic_level=2,
        avg_speed_kmh=28,
        hour=18,
        day_of_week=2,
    )
    assert isinstance(eta, float)
    assert eta == 14.18


# Test 3: Severity Model Loads Successfully
def test_severity_model_loads():
    loaded = SeverityService.load_model()
    assert loaded is True
    assert SeverityService.is_loaded() is True


# Test 4: Severity Prediction Works with Valid Image Sample
def test_severity_prediction_valid_sample():
    img = Image.new("RGB", (224, 224), color="red")
    res = SeverityService.predict_severity(img)
    assert isinstance(res, dict)
    assert "severity" in res
    assert res["severity"] in ("LOW", "MODERATE", "CRITICAL")
    assert "confidence" in res
    assert "probabilities" in res
    assert "suggested_priority" in res
    assert res["suggested_priority"] in ("NORMAL", "HIGH", "CRITICAL")


# Test 5: Emergency Creation Endpoint Works
@pytest.mark.asyncio
async def test_emergency_creation_endpoint():
    img_bytes = create_dummy_image_bytes()
    files = {
        "front_photo": ("front.jpg", img_bytes, "image/jpeg"),
        "rear_photo": ("rear.jpg", img_bytes, "image/jpeg"),
    }
    data = {
        "latitude": "12.9716",
        "longitude": "77.5946",
        "accuracy": "5.0",
        "patient_id": "TEST_PATIENT_101",
    }

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/v1/emergencies", files=files, data=data)

    assert response.status_code == 201
    res_json = response.json()
    assert res_json["success"] is True
    assert "emergency_id" in res_json
    assert res_json["status"] == "SEARCHING"
    assert "priority" in res_json


# Test 6, 7, 8, 9: Full Dispatch & Lifecycle Integration
@pytest.mark.asyncio
async def test_full_emergency_dispatch_lifecycle():
    async with AsyncSessionLocal() as db:
        # 1. Create candidate driver in DB
        import uuid
        driver_id = f"DRV-TEST-{uuid.uuid4().hex[:8]}"
        driver = Driver(
            id=driver_id,
            full_name="Test Driver",
            mobile_number=f"99{uuid.uuid4().int % 100000000:08d}",
            email=f"test_{uuid.uuid4().hex[:8]}@example.com",
            hashed_password="hashed_pw",
            verification_status=VerificationStatus.VERIFIED.value,
            duty_status=DutyStatus.ONLINE.value,
            availability_status=AvailabilityStatus.AVAILABLE.value,
        )
        db.add(driver)
        await db.commit()

        # 2. Add driver location ping
        loc = DriverLocation(
            driver_id=driver_id,
            latitude=12.9720,
            longitude=77.5950,
            accuracy_meters=5.0,
            recorded_at=datetime.now(timezone.utc),
        )
        db.add(loc)
        await db.commit()

        # 3. Create Emergency in DB
        emergency = Emergency(
            patient_id="TEST_PATIENT_LIFECYCLE",
            front_photo_path="/uploads/test_front.jpg",
            rear_photo_path="/uploads/test_rear.jpg",
            latitude=12.9716,
            longitude=77.5946,
            accuracy=5.0,
            status=EmergencyStatus.SEARCHING.value,
            priority="CRITICAL",
        )
        db.add(emergency)
        await db.commit()
        await db.refresh(emergency)

        emergency_id_str = str(emergency.id)

        # 4. Dispatch to candidate
        dispatch_result = await DispatchService.dispatch_to_next_candidate(
            db=db,
            emergency_id_str=emergency_id_str,
            traffic_level=2,
            avg_speed_kmh=30.0,
        )
        assert dispatch_result is not None
        assert dispatch_result["driver_id"] == driver_id
        assert "eta_minutes" in dispatch_result

        # 5. Driver ACCEPTS dispatch
        resp_record = await DispatchService.respond_to_dispatch(
            db=db,
            driver=driver,
            request_id_str=emergency_id_str,
            action_str="ACCEPT",
        )
        assert resp_record.action == "ACCEPT"

        # Check emergency status is ACCEPTED
        await db.refresh(emergency)
        assert emergency.status == EmergencyStatus.ACCEPTED.value
        assert emergency.assigned_driver_id == driver_id

        # 6. Complete Incident
        completed_emergency = await DispatchService.complete_incident(
            db=db,
            driver=driver,
            request_id_str=emergency_id_str,
        )
        assert completed_emergency.status == EmergencyStatus.COMPLETED.value


# Test 10: ML Failure Does Not Crash Emergency Creation
@pytest.mark.asyncio
async def test_ml_failure_graceful_fallback(monkeypatch):
    img_bytes = create_dummy_image_bytes()

    def mock_failing_predict(cls, *args, **kwargs):
        raise RuntimeError("Simulated ML model prediction failure")

    monkeypatch.setattr(SeverityService, "predict_severity", classmethod(mock_failing_predict))

    files = {
        "front_photo": ("front.jpg", img_bytes, "image/jpeg"),
        "rear_photo": ("rear.jpg", img_bytes, "image/jpeg"),
    }
    data = {
        "latitude": "12.9716",
        "longitude": "77.5946",
        "accuracy": "5.0",
        "patient_id": "TEST_PATIENT_FALLBACK",
    }

    # Endpoint must succeed (201 Created) even if ML prediction fails
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/v1/emergencies", files=files, data=data)

    assert response.status_code == 201
    res_json = response.json()
    assert res_json["success"] is True
    assert res_json["status"] == "SEARCHING"
    assert res_json["priority"] == "CRITICAL"
