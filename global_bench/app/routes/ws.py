from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.deps import ws_manager

router = APIRouter(tags=["WebSocket"])


@router.websocket("/ws/progress/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    await ws_manager.connect(websocket, session_id)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket, session_id)
