import asyncio
import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from fastapi import HTTPException, status

from app.models.driver import Driver, VerificationStatus, DutyStatus, AvailabilityStatus
from app.models.driver_location import DriverLocation
from app.models.emergency import Emergency, EmergencyStatus
from app.models.emergency_response import EmergencyResponse, ResponseAction
from app.models.ambulance import Ambulance
from app.utils.distance import haversine_distance_km
from app.websocket.manager import manager as ws_manager
from app.services.eta_service import ETAService

logger = logging.getLogger("dispatch_service")

TIMEOUT_PRIORITY_MAP = {
    "CRITICAL": 20,
    "HIGH": 40,
    "NORMAL": 60,
}


class DispatchService:
    @staticmethod
    async def get_latest_driver_location(db: AsyncSession, driver_id: str) -> Optional[DriverLocation]:
        stmt = (
            select(DriverLocation)
            .where(DriverLocation.driver_id == driver_id)
            .order_by(desc(DriverLocation.recorded_at))
            .limit(1)
        )
        return (await db.execute(stmt)).scalar_one_or_none()

    @staticmethod
    async def find_eligible_candidates(
        db: AsyncSession,
        pickup_lat: float,
        pickup_lon: float,
        max_stale_seconds: int = 60,
    ) -> List[Dict[str, Any]]:
        # Query drivers with VERIFIED, ONLINE, AVAILABLE status
        stmt = select(Driver).where(
            Driver.verification_status == VerificationStatus.VERIFIED.value,
            Driver.duty_status == DutyStatus.ONLINE.value,
            Driver.availability_status == AvailabilityStatus.AVAILABLE.value,
        )
        drivers = (await db.execute(stmt)).scalars().all()

        now = datetime.now(timezone.utc)
        candidates = []

        for driver in drivers:
            loc = await DispatchService.get_latest_driver_location(db, driver.id)
            if not loc:
                continue

            # Check for stale location
            rec_at = loc.recorded_at
            if rec_at.tzinfo is None:
                rec_at = rec_at.replace(tzinfo=timezone.utc)

            time_diff = (now - rec_at).total_seconds()
            if time_diff > max_stale_seconds:
                continue

            dist_km = haversine_distance_km(pickup_lat, pickup_lon, loc.latitude, loc.longitude)
            candidates.append({
                "driver": driver,
                "location": loc,
                "distance_km": dist_km,
            })

        # Sort candidate drivers by distance ascending
        candidates.sort(key=lambda c: c["distance_km"])
        return candidates

    @staticmethod
    async def dispatch_to_next_candidate(
        db: AsyncSession,
        emergency_id_str: str,
        traffic_level: Optional[int] = None,
        avg_speed_kmh: Optional[float] = None,
    ) -> Optional[Dict[str, Any]]:
        try:
            emergency_uuid = uuid.UUID(emergency_id_str)
        except ValueError:
            return None

        stmt = select(Emergency).where(Emergency.id == emergency_uuid).with_for_update()
        emergency = (await db.execute(stmt)).scalar_one_or_none()

        if not emergency or emergency.status != EmergencyStatus.SEARCHING.value:
            return None

        # Fetch drivers who have already responded (ACCEPT, REJECT, or TIMEOUT)
        resp_stmt = select(EmergencyResponse.driver_id).where(EmergencyResponse.request_id == emergency_id_str)
        responded_driver_ids = set((await db.execute(resp_stmt)).scalars().all())

        all_candidates = await DispatchService.find_eligible_candidates(
            db=db,
            pickup_lat=emergency.latitude,
            pickup_lon=emergency.longitude,
        )

        eligible_candidates = [c for c in all_candidates if c["driver"].id not in responded_driver_ids]

        if not eligible_candidates:
            emergency.current_candidate_driver_id = None
            emergency.response_deadline = None
            await db.commit()
            return None

        top_candidate = eligible_candidates[0]
        driver: Driver = top_candidate["driver"]
        dist_km: float = top_candidate["distance_km"]

        priority_upper = (emergency.priority or "CRITICAL").upper()
        timeout_seconds = TIMEOUT_PRIORITY_MAP.get(priority_upper, 60)

        now = datetime.now(timezone.utc)
        deadline = now + timedelta(seconds=timeout_seconds)

        emergency.current_candidate_driver_id = driver.id
        emergency.dispatch_offered_at = now
        emergency.response_deadline = deadline
        await db.commit()

        # Compute optional ETA via ML model if traffic/speed inputs are provided
        eta_minutes = ETAService.predict_eta_safe(
            distance_km=dist_km,
            traffic_level=traffic_level,
            avg_speed_kmh=avg_speed_kmh,
            hour=now.hour,
            day_of_week=now.weekday(),
        )

        # Send WebSocket offer notification to candidate driver with complete details
        created_at_iso = emergency.created_at.isoformat() if emergency.created_at else now.isoformat()
        ws_payload = {
            "emergencyId": str(emergency.id),
            "emergencyType": emergency.emergency_type or "MEDICAL_EMERGENCY",
            "priority": priority_upper,
            "patient": {
                "name": emergency.patient_name or emergency.patient_id,
                "phone": emergency.patient_phone or "",
                "photoUrl": f"/api/v1/emergencies/{emergency.id}/photos/front"
            },
            "pickupLocation": {
                "latitude": emergency.latitude,
                "longitude": emergency.longitude,
            },
            "pickup": {
                "latitude": emergency.latitude,
                "longitude": emergency.longitude,
            },
            "createdAt": created_at_iso,
            "responseDeadline": deadline.isoformat(),
            "timeoutSeconds": timeout_seconds,
            "distanceKm": round(dist_km, 2),
        }
        if eta_minutes is not None:
            ws_payload["etaMinutes"] = eta_minutes

        await ws_manager.send_event_to_driver(
            driver_id=driver.id,
            event_type="EMERGENCY_DISPATCH",
            data=ws_payload,
        )

        # Schedule automatic background timeout task
        asyncio.create_task(
            DispatchService.schedule_timeout_check(
                emergency_id_str=emergency_id_str,
                offered_driver_id=driver.id,
                timeout_seconds=timeout_seconds,
            )
        )

        return {
            "driver_id": driver.id,
            "distance_km": dist_km,
            "timeout_seconds": timeout_seconds,
            "response_deadline": deadline,
            "eta_minutes": eta_minutes,
        }

    @staticmethod
    async def schedule_timeout_check(
        emergency_id_str: str,
        offered_driver_id: str,
        timeout_seconds: int,
    ):
        await asyncio.sleep(timeout_seconds)

        from app.database.database import AsyncSessionLocal
        async with AsyncSessionLocal() as db:
            try:
                emergency_uuid = uuid.UUID(emergency_id_str)
                stmt = select(Emergency).where(Emergency.id == emergency_uuid).with_for_update()
                emergency = (await db.execute(stmt)).scalar_one_or_none()

                if not emergency:
                    return

                # Prevent duplicate / stale timeout processing
                if (
                    emergency.status != EmergencyStatus.SEARCHING.value
                    or emergency.current_candidate_driver_id != offered_driver_id
                ):
                    return

                now = datetime.now(timezone.utc)

                # Record TIMEOUT response entry
                resp_record = EmergencyResponse(
                    request_id=emergency_id_str,
                    driver_id=offered_driver_id,
                    action=ResponseAction.TIMEOUT.value,
                    response_timestamp=now,
                )
                db.add(resp_record)

                # Keep driver AVAILABLE if still ONLINE
                driver_stmt = select(Driver).where(Driver.id == offered_driver_id)
                driver = (await db.execute(driver_stmt)).scalar_one_or_none()
                if driver and driver.duty_status == DutyStatus.ONLINE.value:
                    driver.availability_status = AvailabilityStatus.AVAILABLE.value
                    driver.updated_at = now

                emergency.current_candidate_driver_id = None
                emergency.response_deadline = None
                await db.commit()

                # Send WS event for timeout
                await ws_manager.send_event_to_driver(
                    driver_id=offered_driver_id,
                    event_type="DISPATCH_TIMEOUT",
                    data={
                        "requestId": emergency_id_str,
                        "status": "TIMEOUT",
                    },
                )

                # Automatically trigger dispatch to next eligible candidate
                await DispatchService.dispatch_to_next_candidate(db, emergency_id_str)

            except Exception as e:
                await db.rollback()
                logger.error(f"Error in schedule_timeout_check for {emergency_id_str}: {e}")

    @staticmethod
    async def respond_to_dispatch(
        db: AsyncSession,
        driver: Driver,
        request_id_str: str,
        action_str: str,
    ) -> EmergencyResponse:
        action_upper = action_str.upper()
        if action_upper not in [ResponseAction.ACCEPT.value, ResponseAction.REJECT.value, ResponseAction.TIMEOUT.value]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid action. Allowed actions: ACCEPT, REJECT, TIMEOUT."
            )

        # Parse UUID for Emergency lookup
        try:
            emergency_uuid = uuid.UUID(request_id_str)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid emergency request ID format. Must be a valid UUID."
            )

        now = datetime.now(timezone.utc)

        if action_upper == ResponseAction.ACCEPT.value:
            # Atomic row locking with with_for_update
            stmt = select(Emergency).where(Emergency.id == emergency_uuid).with_for_update()
            emergency = (await db.execute(stmt)).scalar_one_or_none()

            if not emergency:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Emergency request '{request_id_str}' not found."
                )

            # Check if emergency is already assigned, accepted, or offered to someone else
            if emergency.assigned_driver_id or emergency.status in [EmergencyStatus.ACCEPTED.value, EmergencyStatus.ASSIGNED.value, EmergencyStatus.COMPLETED.value]:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Incident already assigned to another responder"
                )

            if emergency.current_candidate_driver_id and emergency.current_candidate_driver_id != driver.id:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Incident dispatch offer expired or assigned to another responder"
                )

            # Assign emergency to driver and set state
            emergency.assigned_driver_id = driver.id
            emergency.current_candidate_driver_id = None
            emergency.response_deadline = None
            emergency.status = EmergencyStatus.ACCEPTED.value
            emergency.accepted_at = now

            # Update driver availability to BUSY
            driver.availability_status = AvailabilityStatus.BUSY.value
            driver.updated_at = now

        else:
            # REJECT or TIMEOUT: Driver remains AVAILABLE
            stmt = select(Emergency).where(Emergency.id == emergency_uuid).with_for_update()
            emergency = (await db.execute(stmt)).scalar_one_or_none()
            if not emergency:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Emergency request '{request_id_str}' not found."
                )

            if emergency.current_candidate_driver_id == driver.id:
                emergency.current_candidate_driver_id = None
                emergency.response_deadline = None

            if driver.duty_status == DutyStatus.ONLINE.value:
                driver.availability_status = AvailabilityStatus.AVAILABLE.value
                driver.updated_at = now

        # Record emergency response entry
        resp_record = EmergencyResponse(
            request_id=request_id_str,
            driver_id=driver.id,
            action=action_upper,
            response_timestamp=now,
        )
        db.add(resp_record)

        await db.commit()
        await db.refresh(resp_record)

        # Notify via WebSocket if active connection exists
        await ws_manager.send_event_to_driver(
            driver_id=driver.id,
            event_type="DISPATCH_RESPONSE_ACK",
            data={
                "requestId": request_id_str,
                "action": action_upper,
                "status": emergency.status
            }
        )

        if action_upper == ResponseAction.ACCEPT.value:
            # Fetch driver ambulance profile
            amb_stmt = select(Ambulance).where(Ambulance.driver_id == driver.id)
            ambulance = (await db.execute(amb_stmt)).scalar_one_or_none()

            # 1. Send DRIVER_ASSIGNED event to Patient WebSocket
            driver_assigned_payload = {
                "emergencyId": request_id_str,
                "driver": {
                    "driverId": driver.id,
                    "name": driver.full_name
                },
                "ambulance": {
                    "ambulanceId": ambulance.id if ambulance else None,
                    "registrationNumber": ambulance.registration_number if ambulance else None,
                    "ambulanceType": ambulance.ambulance_type if ambulance else "BLS"
                },
                "assignedAt": now.isoformat()
            }
            await ws_manager.send_event_to_patient(key=request_id_str, event_type="DRIVER_ASSIGNED", data=driver_assigned_payload)
            if emergency.patient_id:
                await ws_manager.send_event_to_patient(key=emergency.patient_id, event_type="DRIVER_ASSIGNED", data=driver_assigned_payload)

            # 2. Send PATIENT_LOCATION event to Driver WebSocket
            patient_loc_payload = {
                "emergencyId": request_id_str,
                "latitude": emergency.latitude,
                "longitude": emergency.longitude,
                "accuracy": emergency.accuracy
            }
            await ws_manager.send_event_to_driver(driver_id=driver.id, event_type="PATIENT_LOCATION", data=patient_loc_payload)

        # If REJECT or TIMEOUT, trigger dispatch to next candidate automatically
        if action_upper in [ResponseAction.REJECT.value, ResponseAction.TIMEOUT.value]:
            await DispatchService.dispatch_to_next_candidate(db, request_id_str)

        return resp_record

    @staticmethod
    async def complete_incident(
        db: AsyncSession,
        driver: Driver,
        request_id_str: str,
    ) -> Emergency:
        try:
            emergency_uuid = uuid.UUID(request_id_str)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid emergency request ID format. Must be a valid UUID."
            )

        stmt = select(Emergency).where(Emergency.id == emergency_uuid).with_for_update()
        emergency = (await db.execute(stmt)).scalar_one_or_none()

        if not emergency:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Emergency request '{request_id_str}' not found."
            )

        now = datetime.now(timezone.utc)
        emergency.status = EmergencyStatus.COMPLETED.value
        emergency.completed_at = now
        emergency.current_candidate_driver_id = None
        emergency.response_deadline = None

        # Make driver AVAILABLE again if online
        if driver.duty_status == DutyStatus.ONLINE.value:
            driver.availability_status = AvailabilityStatus.AVAILABLE.value
        driver.updated_at = now

        await db.commit()
        await db.refresh(emergency)

        completed_payload = {
            "requestId": request_id_str,
            "emergencyId": request_id_str,
            "status": "COMPLETED",
            "completedAt": now.isoformat()
        }

        # Send status update events to Driver and Patient
        await ws_manager.send_event_to_driver(
            driver_id=driver.id,
            event_type="REQUEST_UPDATE",
            data=completed_payload
        )
        await ws_manager.send_event_to_patient(
            key=request_id_str,
            event_type="EMERGENCY_COMPLETED",
            data=completed_payload
        )
        if emergency.patient_id:
            await ws_manager.send_event_to_patient(
                key=emergency.patient_id,
                event_type="EMERGENCY_COMPLETED",
                data=completed_payload
            )

        return emergency
