from fastapi import WebSocket, WebSocketDisconnect
from typing import List, Dict
from datetime import datetime, timezone

# WebSocket connection manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self.connection_metadata: Dict[WebSocket, Dict] = {}
    
    async def connect(self, websocket: WebSocket):
        # Check connection limit (max 10 connections)
        if len(self.active_connections) >= 10:
            await websocket.close(code=1008, reason="Too many connections")
            return
        
        await websocket.accept()
        self.active_connections.append(websocket)
        self.connection_metadata[websocket] = {
            "connected_at": datetime.now(timezone.utc),
            "last_ping": datetime.now(timezone.utc)
        }
    
    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        if websocket in self.connection_metadata:
            del self.connection_metadata[websocket]
    
    def update_ping(self, websocket: WebSocket):
        """Update last ping timestamp for a connection"""
        if websocket in self.connection_metadata:
            self.connection_metadata[websocket]["last_ping"] = datetime.now(timezone.utc)
    
    async def cleanup_stale_connections(self, max_age_seconds=300):
        """Remove connections that haven't pinged in specified seconds (default 5 minutes)"""
        now = datetime.now(timezone.utc)
        stale = []
        for ws, meta in self.connection_metadata.items():
            age = (now - meta["last_ping"]).total_seconds()
            if age > max_age_seconds:
                stale.append(ws)
        
        for ws in stale:
            print(f"🧹 Removing stale WebSocket connection (no ping for {max_age_seconds}s)")
            await self.disconnect(ws)
    
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