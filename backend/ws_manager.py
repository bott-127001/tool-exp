from fastapi import WebSocket, WebSocketDisconnect
from typing import List

# WebSocket connection manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
    
    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
    
    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
    
    async def broadcast(self, data: dict):
        disconnected = []
        for connection in self.active_connections[:]:  # Use slice copy to avoid modification during iteration
            try:
                await connection.send_json(data)
            except (WebSocketDisconnect, RuntimeError, ConnectionError):
                disconnected.append(connection)
            except Exception as e:
                error_msg = str(e).lower()
                if "closed" not in error_msg and "disconnect" not in error_msg and "send" not in error_msg:
                    print(f"❌ WebSocket send error: {e}")
                disconnected.append(connection)
        
        # Remove disconnected connections
        for conn in disconnected:
            self.disconnect(conn)


# Create a single, global instance of the manager
manager = ConnectionManager()