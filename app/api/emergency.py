from fastapi import APIRouter, Depends, File, Form, UploadFile, HTTPException, status, Query, Request
from fastapi.responses import FileResponse
import os

from app.database.database import get_db
from app.services.emergency_service import EmergencyService
from app.services.dispatch_service import DispatchService
from app.services.severity_service import SeverityService
from app.services.eta_service import ETAService
from app.utils.file_utils import validate_image_file, save_upload_file
from app.utils.security import decode_access_token
from app.schemas.emergency import (
    EmergencyCreateResponse,
    EmergencyStatusResponse,
    EmergencyCancelResponse,
    EmergencyDetailSchema,
)

router = APIRouter(prefix="/api/v1/emergencies", tags=["Emergencies"])


@router.post("", response_model=EmergencyCreateResponse, status_code=status.HTTP_201_CREATED)
async def create_emergency(
    front_photo: UploadFile = File(..., description="Front vehicle photo"),
    rear_photo: UploadFile = File(..., description="Rear vehicle photo"),
    latitude: float = Form(..., description="Latitude (-90 to 90)"),
    longitude: float = Form(..., description="Longitude (-180 to 180)"),
    accuracy: float = Form(..., description="GPS accuracy (non-negative)"),
    timestamp: str | None = Form(default=None, description="ISO timestamp string"),
    patient_id: str | None = Form(default=None, description="Patient identifier"),
    device_id: str | None = Form(default=None, description="Device identifier"),
    patient_device_id: str | None = Form(default=None, description="Patient or Device identifier"),
    priority: str | None = Form(default=None, description="Priority: CRITICAL, HIGH, NORMAL"),
    traffic_level: int | None = Form(default=None, description="Traffic level (1=Low, 2=Medium, 3=High)"),
    avg_speed_kmh: float | None = Form(default=None, description="Average speed in km/h"),
    patient_name: str | None = Form(default=None, description="Patient full name"),
    patient_phone: str | None = Form(default=None, description="Patient phone number"),
    pickup_address: str | None = Form(default=None, description="Pickup address description"),
    emergency_type: str | None = Form(default="MEDICAL_EMERGENCY", description="Emergency category"),
    db: AsyncSession = Depends(get_db),
):
    # 1. Identifier validation
    identifier = patient_id or device_id or patient_device_id
    if not identifier or not identifier.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Patient or device identifier is required (patient_id or device_id)."
        )

    # 2. Coordinate & accuracy validation
    if not (-90.0 <= latitude <= 90.0):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Latitude must be between -90 and 90 degrees."
        )

    if not (-180.0 <= longitude <= 180.0):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Longitude must be between -180 and 180 degrees."
        )

    if accuracy < 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Accuracy cannot be negative."
        )

    # 3. Photo validations
    validate_image_file(front_photo, "front_photo")
    validate_image_file(rear_photo, "rear_photo")

    # 4. Save photo files
    front_db_path, front_url = await save_upload_file(front_photo, prefix="front")
    rear_db_path, rear_url = await save_upload_file(rear_photo, prefix="rear")

    # 5. Parse timestamp
    parsed_timestamp: Optional[datetime] = None
    if timestamp:
        try:
            clean_ts = timestamp.replace("Z", "+00:00")
            parsed_timestamp = datetime.fromisoformat(clean_ts)
        except Exception:
            parsed_timestamp = datetime.now(timezone.utc)

    # 6. Run ML Severity Prediction safely
    severity_prediction = SeverityService.predict_severity_safe(front_db_path)
    predicted_severity: Optional[str] = None
    suggested_priority: Optional[str] = None

    if severity_prediction:
        predicted_severity = severity_prediction.get("severity")
        suggested_priority = severity_prediction.get("suggested_priority")

    effective_priority = priority or suggested_priority or "CRITICAL"

    # 7. Create emergency in DB
    emergency = await EmergencyService.create_emergency(
        db=db,
        patient_id=identifier.strip(),
        front_photo_path=front_url,  # Store standard relative URL path
        rear_photo_path=rear_url,
        latitude=latitude,
        longitude=longitude,
        accuracy=accuracy,
        timestamp=parsed_timestamp,
        priority=effective_priority,
        patient_name=patient_name,
        patient_phone=patient_phone,
        pickup_address=pickup_address,
        emergency_type=emergency_type or "MEDICAL_EMERGENCY",
    )

    # 8. Automatically dispatch offer to nearest eligible candidate driver
    dispatch_info = await DispatchService.dispatch_to_next_candidate(
        db=db,
        emergency_id_str=str(emergency.id),
        traffic_level=traffic_level,
        avg_speed_kmh=avg_speed_kmh,
    )

    eta_mins = dispatch_info.get("eta_minutes") if dispatch_info else None

    return EmergencyCreateResponse(
        success=True,
        message="Emergency created successfully",
        emergency_id=str(emergency.id),
        status=emergency.status,
        priority=emergency.priority,
        severity=predicted_severity,
        eta_minutes=eta_mins,
    )


@router.get("/{emergency_id}/photos/{photo_type}")
async def get_emergency_photo(
    emergency_id: str,
    photo_type: str,
    request: Request,
    token: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    if photo_type not in ("front", "rear"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid photo type. Must be 'front' or 'rear'."
        )

    # Resolve token from query param or Authorization header
    auth_token = token
    if not auth_token:
        auth_header = request.headers.get("authorization")
        if auth_header and auth_header.startswith("Bearer "):
            auth_token = auth_header.split(" ")[1]

    if not auth_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication token missing."
        )

    payload = decode_access_token(auth_token)
    caller_id = str(payload.get("driver_id") or payload.get("patient_id") or payload.get("sub") or "")

    emergency = await EmergencyService.get_emergency_by_id(db, emergency_id)

    # Privacy / Authorization check
    is_assigned_driver = emergency.assigned_driver_id and (str(emergency.assigned_driver_id) == caller_id)
    is_offered_driver = emergency.current_candidate_driver_id and (str(emergency.current_candidate_driver_id) == caller_id)
    is_patient = str(emergency.patient_id) == caller_id

    if not (is_assigned_driver or is_offered_driver or is_patient):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. You are not authorized to view photos for this emergency."
        )

    photo_path = emergency.front_photo_path if photo_type == "front" else emergency.rear_photo_path
    if not photo_path:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Photo record not found.")

    safe_filename = os.path.basename(photo_path)
    abs_file_path = os.path.abspath(os.path.join("uploads", "emergencies", safe_filename))

    if not os.path.exists(abs_file_path):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Photo file not found on server.")

    return FileResponse(abs_file_path, media_type="image/jpeg")


@router.get("/{emergency_id}", response_model=EmergencyStatusResponse)
async def get_emergency_status(
    emergency_id: str,
    db: AsyncSession = Depends(get_db),
):
    emergency = await EmergencyService.get_emergency_by_id(db, emergency_id)

    detail = EmergencyDetailSchema(
        id=str(emergency.id),
        patient_id=emergency.patient_id,
        front_photo_url=emergency.front_photo_path,
        rear_photo_url=emergency.rear_photo_path,
        latitude=emergency.latitude,
        longitude=emergency.longitude,
        accuracy=emergency.accuracy,
        timestamp=emergency.timestamp,
        created_at=emergency.created_at,
        status=emergency.status,
        assigned_ambulance_id=emergency.assigned_ambulance_id,
        assigned_driver_id=emergency.assigned_driver_id,
        priority=emergency.priority,
        patient_name=emergency.patient_name,
        patient_phone=emergency.patient_phone,
        pickup_address=emergency.pickup_address,
        emergency_type=emergency.emergency_type,
    )

    return EmergencyStatusResponse(
        success=True,
        emergency_id=str(emergency.id),
        status=emergency.status,
        data=detail,
    )


@router.post("/{emergency_id}/cancel", response_model=EmergencyCancelResponse)
async def cancel_emergency(
    emergency_id: str,
    db: AsyncSession = Depends(get_db),
):
    emergency = await EmergencyService.cancel_emergency(db, emergency_id)

    # Broadcast EMERGENCY_CANCELLED to Patient WS and Driver WS if assigned
    now = datetime.now(timezone.utc)
    cancel_payload = {
        "emergencyId": str(emergency.id),
        "status": "CANCELLED",
        "cancelledAt": now.isoformat()
    }
    await ws_manager.send_event_to_patient(key=str(emergency.id), event_type="EMERGENCY_CANCELLED", data=cancel_payload)
    if emergency.patient_id:
        await ws_manager.send_event_to_patient(key=emergency.patient_id, event_type="EMERGENCY_CANCELLED", data=cancel_payload)
    if emergency.assigned_driver_id:
        await ws_manager.send_event_to_driver(driver_id=emergency.assigned_driver_id, event_type="REQUEST_UPDATE", data=cancel_payload)

    return EmergencyCancelResponse(
        success=True,
        message="Emergency cancelled successfully",
        emergency_id=str(emergency.id),
        status=emergency.status,
    )
