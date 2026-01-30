from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
import uvicorn
from contextlib import asynccontextmanager
import asyncio
from typing import Dict, List
import json
from datetime import datetime, timezone
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv() 

from auth import auth_router, get_frontend_user_from_token_async
from database import init_db, get_user_settings, update_user_settings
from ws_manager import manager # Import the shared manager instance
from pipeline_worker import (
    start_polling, stop_polling, get_latest_data, 
    get_current_user as get_current_authenticated_user,
    reset_baseline as clear_daily_baseline_async, pipeline
)
from greek_signals import detect_signals

# For data export
from fastapi.responses import StreamingResponse
import io


import os

def _is_main_worker():
    """Check if this is the main worker process (first worker)"""
    # Use a file-based lock to ensure only one worker starts background tasks
    # This works across multiple gunicorn workers
    lock_file = "/tmp/background_tasks.lock"
    
    try:
        import fcntl
        # Try to acquire an exclusive lock (non-blocking)
        lock_fd = os.open(lock_file, os.O_CREAT | os.O_WRONLY)
        try:
            fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            # We got the lock, this is the main worker
            return True
        except (IOError, OSError):
            # Lock is held by another process
            os.close(lock_fd)
            return False
    except (ImportError, OSError):
        # fcntl not available (Windows) or file operations failed
        # Fallback: check environment variable set by first worker
        if os.getenv("BACKGROUND_TASKS_STARTED") == "1":
            return False
        os.environ["BACKGROUND_TASKS_STARTED"] = "1"
        return True

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await init_db()
    
    # Only start background tasks in one worker to avoid duplicates
    is_main = _is_main_worker()
    
    if is_main:
        print("Database initialized")
        print("Backend server ready. Polling will start automatically when a user authenticates.")
        
        # Start background polling task (will wait for authentication)
        polling_task = asyncio.create_task(start_polling()) # The worker will use the global manager
        
        # Start automated token refresh scheduler (runs daily at 9:15 AM IST)
        from auto_auth import daily_token_refresh_scheduler
        token_refresh_task = asyncio.create_task(daily_token_refresh_scheduler())
        
        # Start automated token cleanup scheduler (runs daily at 3:00 AM IST)
        # Note: Full daily cleanup is now manual-only via Settings page
        from daily_cleanup import token_cleanup_scheduler
        token_cleanup_task = asyncio.create_task(token_cleanup_scheduler())
        
        # Start data logger (logs all metrics to CSV every 5 seconds during market hours)
        from data_logger import run_logger
        data_logger_task = asyncio.create_task(run_logger())
    else:
        # This is a duplicate worker, just initialize DB
        print("Database initialized (worker process)")
        polling_task = None
        token_refresh_task = None
        token_cleanup_task = None
        data_logger_task = None
    
    yield
    
    # Shutdown
    tasks_to_cancel = []
    
    if polling_task is not None:
        await stop_polling()
        polling_task.cancel()
        tasks_to_cancel.append(polling_task)
    
    if token_refresh_task is not None:
        token_refresh_task.cancel()
        tasks_to_cancel.append(token_refresh_task)
    
    if token_cleanup_task is not None:
        token_cleanup_task.cancel()
        tasks_to_cancel.append(token_cleanup_task)
    
    if data_logger_task is not None:
        data_logger_task.cancel()
        tasks_to_cancel.append(data_logger_task)
    
    for task in tasks_to_cancel:
        try:
            await task
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
                        manager.update_ping(websocket)  # Update ping timestamp
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


@app.get("/api/auth/current-user")
async def get_current_user():
    """
    Returns the currently authenticated user, if any.
    """
    user = get_current_authenticated_user()
    return JSONResponse(content={"user": user})


@app.post("/api/reset-baseline")
async def reset_baseline():
    """
    Manually clears the baseline greeks for the current user and the current day
    from the database, forcing a recapture on the next poll.
    """
    user = get_current_authenticated_user()
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    from data_fetcher import clear_daily_baseline
    await clear_daily_baseline(user, today_str)
    await clear_daily_baseline_async()
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
            "consecutive_confirmations": 2,
            "vol_rv_ratio_contraction_threshold": 0.8,
            "vol_rv_ratio_expansion_threshold": 1.5,
            "vol_min_rv_ratio_acceleration": 0.05,
            # Direction & Asymmetry thresholds
            "dir_gap_acceptance_threshold": 0.65,
            "dir_acceptance_neutral_threshold": 0.5,
            "dir_rea_bull_threshold": 0.3,
            "dir_rea_bear_threshold": -0.3,
            "dir_rea_neutral_abs_threshold": 0.3,
            "dir_de_directional_threshold": 0.5,
            "dir_de_neutral_threshold": 0.3,
            # Optional previous-day inputs (for Opening Location & Gap Acceptance)
            "prev_day_close": None,
            "prev_day_range": None,
            "prev_day_date": None,  # ISO date string of the provided previous-day stats
        }
    
    # Convert ObjectId to string to avoid JSON serialization error
    if "_id" in settings:
        settings["_id"] = str(settings["_id"])
        
    return settings


@app.put("/api/settings/{user}")
async def update_settings(user: str, settings: dict):
    """Update user settings"""
    updated = await update_user_settings(user, settings)
    if not updated:
        raise HTTPException(status_code=404, detail="User not found")
        
    # Convert ObjectId to string to avoid JSON serialization error
    if "_id" in updated:
        updated["_id"] = str(updated["_id"])
        
    return {"message": "Settings updated", "settings": updated}


@app.get("/api/logs/{user}")
async def get_trade_logs(user: str):
    """Get trade logs for a user"""
    from database import get_trade_logs
    logs = await get_trade_logs(user)
    return {"logs": logs}


@app.api_route("/health-check", methods=["GET", "HEAD"])
async def health_check(request: Request):
    """
    Endpoint for uptime monitoring to prevent the service from spinning down.
    This endpoint is publicly accessible (no authentication required) and supports both GET and HEAD requests.
    HEAD requests return a 200 status with no body, which is required for UptimeRobot monitoring.
    """
    # print("Health check ping received.")  # Good for debugging
    response_data = {"status": "ok", "timestamp": datetime.now().isoformat()}
    
    # For HEAD requests, return response with no body (status 200)
    # This is required for proper HTTP HEAD request handling
    if request.method == "HEAD":
        return Response(status_code=200)
    
    # For GET requests, return JSON response
    return response_data


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


@app.delete("/api/clear-data")
async def clear_market_data():
    """
    Manual trigger for daily cleanup tasks.
    Performs:
    1. Clear daily_baselines from database
    2. Clear market_data_log collection
    3. Reset in-memory state (baseline_greeks, price_history, latest_data)
    
    NOTE: Does NOT null out tokens (use /api/clear-tokens endpoint for that).
    """
    user = get_current_authenticated_user()
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")

    from database import market_data_log_collection, db
    from daily_cleanup import clear_daily_baselines, reset_in_memory_state
    
    results = {}
    
    try:
        # Step 1: Clear daily_baselines
        baseline_count = await clear_daily_baselines()
        results["baselines_cleared"] = baseline_count
        
        # Step 2: Clear market_data_log
        market_data_result = await market_data_log_collection.delete_many({})
        results["market_data_cleared"] = market_data_result.deleted_count
        
        # Step 3: Reset in-memory state
        await reset_in_memory_state()
        results["in_memory_reset"] = True
        
        return {
            "message": "Daily cleanup tasks completed successfully",
            "results": results
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error during cleanup: {str(e)}")


@app.delete("/api/clear-tokens")
async def clear_tokens():
    """
    Manual trigger to clear access tokens for all users.
    This nulls out access_token, refresh_token, and token_expires_at.
    
    NOTE: Tokens are also automatically cleared at 3 AM IST daily.
    This endpoint provides a manual trigger option.
    """
    user = get_current_authenticated_user()
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")

    from daily_cleanup import null_out_tokens
    
    try:
        users_modified = await null_out_tokens()
        return {
            "message": f"Access tokens cleared for {users_modified} users",
            "users_modified": users_modified
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error clearing tokens: {str(e)}")


@app.post("/api/fetch-previous-day-data")
async def fetch_previous_day_data(request: Request):
    """
    Manually trigger fetch of previous day's OHLC data for the current frontend user.
    Uses Upstox Historical Candle Data V3 under the hood and stores values in user settings.
    """
    # Frontend authentication via session token
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated")

    session_token = auth_header.split("Bearer ")[1]
    username = await get_frontend_user_from_token_async(session_token)
    if not username:
        raise HTTPException(status_code=401, detail="Invalid session")

    # Fetch and store previous-day data
    from data_fetcher import fetch_and_store_previous_day_data

    ohlc = await fetch_and_store_previous_day_data(username)
    if not ohlc:
        raise HTTPException(status_code=500, detail="Failed to fetch previous-day data from Upstox")

    return {
        "success": True,
        "username": username,
        "prev_day_close": ohlc["close"],
        "prev_day_high": ohlc["high"],
        "prev_day_low": ohlc["low"],
        "prev_day_range": ohlc["range"],
        "prev_day_date": ohlc["date"],
    }


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
