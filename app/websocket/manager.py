import json
import logging
from typing import Dict, Set
from fastapi import WebSocket

logger = logging.getLogger("websocket_manager")


class ConnectionManager:
    def __init__(self):
        # Maps driver_id -> WebSocket connection
        self.active_connections: Dict[str, WebSocket] = {}
        # Maps emergency_id or patient_id -> Set[WebSocket]
        self.patient_connections: Dict[str, Set[WebSocket]] = {}

    async def connect(self, driver_id: str, websocket: WebSocket):
        await websocket.accept()
        self.active_connections[driver_id] = websocket
        logger.info(f"Driver '{driver_id}' connected via WebSocket.")

    def disconnect(self, driver_id: str):
        if driver_id in self.active_connections:
            del self.active_connections[driver_id]
            logger.info(f"Driver '{driver_id}' disconnected from WebSocket.")

    async def send_event_to_driver(self, driver_id: str, event_type: str, data: dict) -> bool:
        """
        Sends a JSON event to a specific driver if connected.
        Includes both 'type' and 'event' keys for client compatibility.
        """
        websocket = self.active_connections.get(driver_id)
        if websocket:
            try:
                payload = {
                    "type": event_type,
                    "event": event_type,
                    "data": data
                }
                await websocket.send_text(json.dumps(payload))
                return True
            except Exception as e:
                logger.error(f"Error sending WS event to driver {driver_id}: {e}")
                self.disconnect(driver_id)
                return False
        return False

    async def connect_patient(self, key: str, websocket: WebSocket):
        await websocket.accept()
        if key not in self.patient_connections:
            self.patient_connections[key] = set()
        self.patient_connections[key].add(websocket)
        logger.info(f"Patient key '{key}' connected via WebSocket.")

    def disconnect_patient(self, key: str, websocket: WebSocket):
        if key in self.patient_connections:
            self.patient_connections[key].discard(websocket)
            if not self.patient_connections[key]:
                del self.patient_connections[key]
            logger.info(f"Patient key '{key}' disconnected from WebSocket.")

    async def send_event_to_patient(self, key: str, event_type: str, data: dict) -> bool:
        """
        Sends a JSON event to all connected Patient WebSockets for an emergency_id or patient_id.
        """
        ws_set = self.patient_connections.get(key)
        if not ws_set:
            return False
        payload = {
            "type": event_type,
            "event": event_type,
            "data": data
        }
        msg = json.dumps(payload)
        to_remove = set()
        sent = False
        for ws in list(ws_set):
            try:
                await ws.send_text(msg)
                sent = True
            except Exception as e:
                logger.error(f"Error sending WS event to patient {key}: {e}")
                to_remove.add(ws)
        for ws in to_remove:
            self.disconnect_patient(key, ws)
        return sent

    async def broadcast_event(self, event_type: str, data: dict):
        payload = {
            "type": event_type,
            "event": event_type,
            "data": data
        }
        message = json.dumps(payload)
        for driver_id, connection in list(self.active_connections.items()):
            try:
                await connection.send_text(message)
            except Exception as e:
                logger.error(f"Error broadcasting WS event to {driver_id}: {e}")
                self.disconnect(driver_id)


manager = ConnectionManager()
