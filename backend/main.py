from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
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
from data_fetcher import start_polling, stop_polling, get_latest_data
from greek_signals import detect_signals, get_aggregated_greeks
from calc import aggregate_call_put_greeks

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
    init_db()
    print("Database initialized")
    print("Backend server ready. Polling will start automatically when a user authenticates.")
    
    # Start background polling task (will wait for authentication)
    polling_task = asyncio.create_task(start_polling(manager))
    
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


@app.get("/api/dashboard")
async def get_dashboard_data():
    """Get current dashboard data"""
    data = get_latest_data()
    if not data:
        # Return empty structure instead of 404 - allows dashboard to load
        return {
            "timestamp": None,
            "underlying_price": None,
            "atm_strike": None,
            "expiry_date": None,
            "aggregated_greeks": {
                "call": {"delta": 0, "vega": 0, "theta": 0, "gamma": 0, "option_count": 0},
                "put": {"delta": 0, "vega": 0, "theta": 0, "gamma": 0, "option_count": 0}
            },
            "signals": [],
            "option_count": 0,
            "message": "Waiting for market data..."
        }
    return data


@app.get("/api/settings/{user}")
async def get_settings(user: str):
    """Get user settings"""
    settings = get_user_settings(user)
    if not settings:
        raise HTTPException(status_code=404, detail="Settings not found")
    return settings


@app.put("/api/settings/{user}")
async def update_settings(user: str, settings: dict):
    """Update user settings"""
    updated = update_user_settings(user, settings)
    if not updated:
        raise HTTPException(status_code=404, detail="User not found")
    return {"message": "Settings updated", "settings": updated}


@app.get("/api/logs/{user}")
async def get_trade_logs(user: str):
    """Get trade logs for a user"""
    from database import get_trade_logs
    logs = get_trade_logs(user)
    return {"logs": logs}


@app.get("/api/option-chain")
async def get_option_chain():
    """Get normalized option chain data"""
    from data_fetcher import get_raw_option_chain
    raw_chain = get_raw_option_chain()
    if not raw_chain:
        return {
            "timestamp": None,
            "underlying_price": None,
            "atm_strike": None,
            "expiry_date": None,
            "options": [],
            "message": "Waiting for market data..."
        }
    else:
        from data_fetcher import normalize_option_chain
        normalized = normalize_option_chain(raw_chain)
        return normalized or {} # Return normalized data or an empty dict on failure


@app.get("/health-check")
async def health_check():
    """Endpoint for uptime monitoring to prevent the service from spinning down."""
    print("Health check ping received.")  # Good for debugging
    return {"status": "ok", "timestamp": datetime.now().isoformat()}


@app.get("/api/export-data")
async def export_data():
    """Exports the collected market data log as a CSV file."""
    from database import get_db_connection
    import csv

    output = io.StringIO()
    writer = csv.writer(output)

    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=500, detail="Database connection failed")

    try:
        cursor = conn.cursor()
        cursor.execute("SELECT timestamp, underlying_price, atm_strike, aggregated_greeks, signals FROM market_data_log ORDER BY timestamp")
        writer.writerow([description[0] for description in cursor.description])  # Write headers
        for row in cursor:
            writer.writerow(row)
    finally:
        conn.close()

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
