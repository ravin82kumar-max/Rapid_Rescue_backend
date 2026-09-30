import logging
from typing import Optional
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, status, Query

from app.utils.security import decode_access_token
from app.websocket.manager import manager as ws_manager

logger = logging.getLogger("websocket")
router = APIRouter(tags=["WebSocket"])


@router.websocket("/ws/driver")
async def driver_websocket_endpoint(
    websocket: WebSocket,
    token: Optional[str] = Query(None),
):
    if not token:
        # Check authorization header if query param token not supplied
        auth_header = websocket.headers.get("authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]

    if not token:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    try:
        payload = decode_access_token(token)
        driver_id = payload.get("driver_id") or payload.get("sub")
        if not driver_id:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return
    except Exception as e:
        logger.error(f"WebSocket auth failed: {e}")
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    await ws_manager.connect(driver_id, websocket)
    try:
        while True:
            # Keep connection open and receive optional client messages/pings
            data = await websocket.receive_text()
            logger.info(f"Received WS message from driver {driver_id}: {data}")
    except WebSocketDisconnect:
        ws_manager.disconnect(driver_id)
    except Exception as e:
        logger.error(f"WebSocket error for driver {driver_id}: {e}")
        ws_manager.disconnect(driver_id)


@router.websocket("/ws/patient")
async def patient_websocket_endpoint(
    websocket: WebSocket,
    token: Optional[str] = Query(None),
    emergency_id: Optional[str] = Query(None),
    patient_id: Optional[str] = Query(None),
):
    if not token:
        auth_header = websocket.headers.get("authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]

    sub_key = emergency_id or patient_id

    if token:
        try:
            payload = decode_access_token(token)
            sub_key = sub_key or payload.get("emergency_id") or payload.get("patient_id") or payload.get("sub")
        except Exception as e:
            logger.warning(f"Patient WebSocket token decoding failed: {e}")

    if not sub_key:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    sub_key_str = str(sub_key)
    await ws_manager.connect_patient(sub_key_str, websocket)

    try:
        # Send initial status event on connect
        await ws_manager.send_event_to_patient(
            key=sub_key_str,
            event_type="EMERGENCY_SEARCHING",
            data={
                "emergencyId": sub_key_str,
                "status": "SEARCHING"
            }
        )
        while True:
            data = await websocket.receive_text()
            logger.info(f"Received WS message from patient {sub_key_str}: {data}")
    except WebSocketDisconnect:
        ws_manager.disconnect_patient(sub_key_str, websocket)
    except Exception as e:
        logger.error(f"WebSocket error for patient {sub_key_str}: {e}")
        ws_manager.disconnect_patient(sub_key_str, websocket)
