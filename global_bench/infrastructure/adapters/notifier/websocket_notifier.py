from typing import Dict, List
from fastapi import WebSocket
from domain.ports.notifier import NotifierPort

class ConnectionManager:
    def __init__(self):
        # On stocke les connexions par session_id pour ne pas polluer tout le monde
        self.active_connections: Dict[str, List[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, session_id: str):
        await websocket.accept()
        if session_id not in self.active_connections:
            self.active_connections[session_id] = []
        self.active_connections[session_id].append(websocket)

    def disconnect(self, websocket: WebSocket, session_id: str):
        if session_id in self.active_connections:
            self.active_connections[session_id].remove(websocket)

    async def broadcast_to_session(self, session_id: str, message: dict):
        if session_id in self.active_connections:
            for connection in self.active_connections[session_id]:
                await connection.send_json(message)

class WebSocketNotifier(NotifierPort):
    def __init__(self, manager: ConnectionManager):
        self.manager = manager

    async def publish_progress(self, data: dict):
        session_id = data.get("session_id")
        if session_id is None:
            raise ValueError("No session id provided")
        session_id = str(session_id)
        await self.manager.broadcast_to_session(session_id, data)