from datetime import datetime, timezone
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database.database import get_db
from app.models.driver import Driver
from app.models.driver_location import DriverLocation
from app.models.emergency import Emergency, EmergencyStatus
from app.models.ambulance import Ambulance
from app.utils.security import get_current_driver
from app.utils.distance import haversine_distance_km
from app.services.eta_service import ETAService
from app.websocket.manager import manager as ws_manager
from app.schemas.location import LocationUpdateSchema, LocationUpdateResponse

router = APIRouter(prefix="/api/v1/drivers/me", tags=["Location"])


@router.post("/location", response_model=LocationUpdateResponse, status_code=status.HTTP_201_CREATED)
async def update_location(
    data: LocationUpdateSchema,
    current_driver: Driver = Depends(get_current_driver),
    db: AsyncSession = Depends(get_db),
):
    now = datetime.now(timezone.utc)

    # Parse timestamp if supplied
    recorded_at = now
    if data.timestamp:
        try:
            if isinstance(data.timestamp, (int, float)):
                # epoch ms or s
                ts_val = data.timestamp / 1000.0 if data.timestamp > 1e11 else data.timestamp
                recorded_at = datetime.fromtimestamp(ts_val, tz=timezone.utc)
            elif isinstance(data.timestamp, str):
                recorded_at = datetime.fromisoformat(data.timestamp.replace("Z", "+00:00"))
        except Exception:
            recorded_at = now

    location_entry = DriverLocation(
        driver_id=current_driver.id,
        latitude=data.latitude,
        longitude=data.longitude,
        accuracy_meters=data.accuracy,
        altitude_meters=data.altitude,
        heading_degrees=data.heading,
        speed_mps=data.speed,
        recorded_at=recorded_at,
    )

    db.add(location_entry)
    await db.commit()

    # Check for active assigned emergency for live tracking broadcast to patient
    stmt = select(Emergency).where(
        Emergency.assigned_driver_id == current_driver.id,
        Emergency.status.in_([
            EmergencyStatus.ACCEPTED.value,
            EmergencyStatus.ASSIGNED.value,
            EmergencyStatus.IN_PROGRESS.value
        ])
    )
    result = await db.execute(stmt)
    active_emergency = result.scalar_one_or_none()

    if active_emergency:
        # Fetch ambulance info
        amb_stmt = select(Ambulance).where(Ambulance.driver_id == current_driver.id)
        ambulance = (await db.execute(amb_stmt)).scalar_one_or_none()

        em_id_str = str(active_emergency.id)

        driver_loc_payload = {
            "emergencyId": em_id_str,
            "driverId": current_driver.id,
            "ambulanceId": ambulance.id if ambulance else None,
            "latitude": data.latitude,
            "longitude": data.longitude,
            "accuracy": data.accuracy or 5.0,
            "speedMps": data.speed or 0.0,
            "headingDegrees": data.heading or 0.0,
            "recordedAt": recorded_at.isoformat()
        }

        # Broadcast live driver GPS to patient
        await ws_manager.send_event_to_patient(key=em_id_str, event_type="DRIVER_LOCATION_UPDATE", data=driver_loc_payload)
        if active_emergency.patient_id:
            await ws_manager.send_event_to_patient(key=active_emergency.patient_id, event_type="DRIVER_LOCATION_UPDATE", data=driver_loc_payload)

        # Calculate distance and updated ETA
        dist_km = haversine_distance_km(active_emergency.latitude, active_emergency.longitude, data.latitude, data.longitude)
        
        # Calculate speed in km/h if available from speed_mps
        avg_speed = (data.speed * 3.6) if (data.speed and data.speed > 0) else None

        eta_mins = ETAService.predict_eta_safe(
            distance_km=dist_km,
            avg_speed_kmh=avg_speed,
            hour=recorded_at.hour,
            day_of_week=recorded_at.weekday()
        )

        eta_payload = {
            "emergencyId": em_id_str,
            "distanceKm": round(dist_km, 2),
            "etaMinutes": eta_mins,
            "updatedAt": recorded_at.isoformat()
        }

        # Broadcast ETA update to both Patient and Driver
        await ws_manager.send_event_to_patient(key=em_id_str, event_type="ETA_UPDATE", data=eta_payload)
        if active_emergency.patient_id:
            await ws_manager.send_event_to_patient(key=active_emergency.patient_id, event_type="ETA_UPDATE", data=eta_payload)
        await ws_manager.send_event_to_driver(driver_id=current_driver.id, event_type="ETA_UPDATE", data=eta_payload)

    return LocationUpdateResponse(
        success=True,
        message="Location updated successfully",
        recordedAt=recorded_at.isoformat(),
    )
