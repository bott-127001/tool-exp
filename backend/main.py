from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
import uvicorn
from contextlib import asynccontextmanager
import asyncio
from typing import Dict, List
import json
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv() 

from auth import auth_router
from database import init_db, get_user_settings, update_user_settings
from data_fetcher import start_polling, stop_polling, get_latest_data, get_current_authenticated_user, clear_daily_baseline
from greek_signals import detect_signals

# For data export
from fastapi.responses import StreamingResponse
import io

# WebSocket connection manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
    
    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
    
    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)
    
    async def broadcast(self, data: dict):
        disconnected = []
        for connection in self.active_connections[:]:  # Use slice copy to avoid modification during iteration
            try:
                # Check if connection is still open before sending
                await connection.send_json(data)
            except (WebSocketDisconnect, RuntimeError, ConnectionError) as e:
                # These are expected when connection is closed
                disconnected.append(connection)
            except Exception as e:
                # Only log unexpected errors
                error_msg = str(e).lower()
                if "closed" not in error_msg and "disconnect" not in error_msg and "send" not in error_msg:
                    print(f"❌ WebSocket send error: {e}")
                disconnected.append(connection)
        
        # Remove disconnected connections
        for conn in disconnected:
            try:
                self.disconnect(conn)
            except:
                pass


manager = ConnectionManager()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await init_db()
    print("Database initialized")
    print("Backend server ready. Polling will start automatically when a user authenticates.")
    
    # Start background polling task (will wait for authentication)
    polling_task = asyncio.create_task(start_polling(manager)) # Pass the manager instance
    
    yield
    
    # Shutdown
    await stop_polling()
    polling_task.cancel()
    try:
        await polling_task
    except asyncio.CancelledError:
        pass


app = FastAPI(lifespan=lifespan)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include auth router
app.include_router(auth_router, prefix="/api/auth", tags=["auth"])


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    try:
        await manager.connect(websocket)
        
        # Send initial data on connection
        latest_data = get_latest_data()
        if latest_data:
            try:
                await websocket.send_json(latest_data)
            except:
                # Connection closed immediately, exit
                manager.disconnect(websocket)
                return
        
        # Keep connection alive
        while True:
            try:
                message = await asyncio.wait_for(websocket.receive_text(), timeout=60.0)
                
                # Handle ping messages
                try:
                    data = json.loads(message)
                    if data.get("type") == "ping":
                        await websocket.send_json({"type": "pong"})
                except:
                    pass
                    
            except asyncio.TimeoutError:
                # Send ping to keep alive
                try:
                    await websocket.send_json({"type": "ping"})
                except (WebSocketDisconnect, RuntimeError):
                    break
            except WebSocketDisconnect:
                break
    except WebSocketDisconnect:
        pass  # Normal disconnection
    except Exception as e:
        print(f"❌ WebSocket error: {e}")
    finally:
        try:
            manager.disconnect(websocket)
        except:
            pass


@app.get("/test-ws")
async def test_ws():
    """Test endpoint to verify server is running"""
    return {
        "status": "ok",
        "websocket_endpoint": "ws://localhost:8000/ws",
        "active_connections": len(manager.active_connections)
    }


@app.get("/api/auth/current-user")
async def get_current_user():
    """
    Returns the currently authenticated user, if any.
    """
    user = await get_current_authenticated_user()
    return JSONResponse(content={"user": user})


@app.post("/api/reset-baseline")
async def reset_baseline():
    """
    Manually clears the baseline greeks for the current user and the current day
    from the database, forcing a recapture on the next poll.
    """
    user = await get_current_authenticated_user()
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    await clear_daily_baseline(user, today_str) # Add await here
    return {"message": "Baseline greeks for today have been cleared. A new baseline will be captured on the next data poll."}


@app.get("/api/settings/{user}")
async def get_settings(user: str):
    """Get user settings"""
    settings = await get_user_settings(user)
    # If no settings are found for the user, return a default structure.
    # This prevents a 500 error for new users who haven't saved settings yet.
    if not settings:
        return {
            "delta_threshold": 0.20,
            "vega_threshold": 0.10,
            "theta_threshold": 0.02,
            "gamma_threshold": 0.01,
            "consecutive_confirmations": 2
        }
    return settings


@app.put("/api/settings/{user}")
async def update_settings(user: str, settings: dict):
    """Update user settings"""
    updated = await update_user_settings(user, settings)
    if not updated:
        raise HTTPException(status_code=404, detail="User not found")
    return {"message": "Settings updated", "settings": updated}


@app.get("/api/logs/{user}")
async def get_trade_logs(user: str):
    """Get trade logs for a user"""
    from database import get_trade_logs
    logs = await get_trade_logs(user)
    return {"logs": logs}


@app.api_route("/health-check", methods=["GET", "HEAD"])
async def health_check():
    """Endpoint for uptime monitoring to prevent the service from spinning down."""
    # print("Health check ping received.")  # Good for debugging
    return {"status": "ok", "timestamp": datetime.now().isoformat()}


@app.get("/api/export-data")
async def export_data():
    """Exports the collected market data log as a CSV file."""
    from database import market_data_log_collection
    import csv

    output = io.StringIO()
    writer = csv.writer(output)

    # Write headers
    headers = ["timestamp", "underlying_price", "atm_strike", "aggregated_greeks", "signals"]
    writer.writerow(headers)

    # Fetch data from MongoDB
    cursor = market_data_log_collection.find({}, {"_id": 0}).sort("timestamp", 1)
    async for doc in cursor:
        writer.writerow([
            doc.get("timestamp"),
            doc.get("underlying_price"),
            doc.get("atm_strike"),
            json.dumps(doc.get("aggregated_greeks")),
            json.dumps(doc.get("signals"))
        ])

    # Seek to the beginning of the stream
    output.seek(0)
    return StreamingResponse(output, media_type="text/csv", headers={"Content-Disposition": "attachment; filename=market_data_log.csv"})


# --- Static Files and Catch-all ---
# This section must come AFTER all other API routes

@app.get("/api")
async def root():
    """Root API endpoint"""
    return {
        "message": "NIFTY50 Options Greek-Signature Signal System API",
        "status": "running",
    }

# Mount the 'assets' directory from within 'static' to serve JS, CSS, etc.
# This path must match the base path in your frontend build config (Vite)
app.mount("/assets", StaticFiles(directory="static/assets"), name="assets")

# The catch-all route to handle client-side routing (e.g., /dashboard, /settings)
# This must be the LAST route defined.
@app.get("/{full_path:path}")
async def serve_react_app(full_path: str):
    """Serve the React index.html for any path not caught by an API endpoint."""
    from fastapi.responses import FileResponse
    return FileResponse('static/index.html')


if __name__ == "__main__":
    print("\n" + "="*70)
    print("STARTING BACKEND SERVER")
    print("="*70)
    print("Server will start on: http://0.0.0.0:8000")
    print("NOTE: No browser will open automatically!")
    print("You must manually visit: http://localhost:3000/login")
    print("="*70 + "\n")
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
