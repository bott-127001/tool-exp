import json
from datetime import datetime
from typing import Optional, Dict, List
import os
try:
    import motor.motor_asyncio
    from pymongo import MongoClient
    from pymongo.server_api import ServerApi
    from pymongo.errors import ConnectionFailure
except ImportError:
    print("motor/pymongo not found. Please install with 'pip install motor pymongo'.")
    exit(1)

MONGO_URI = os.getenv("MONGO_URI")
client = motor.motor_asyncio.AsyncIOMotorClient(MONGO_URI)
db = client.get_database("option_tool_db")

users_collection = db.get_collection("users")
settings_collection = db.get_collection("user_settings")
trade_logs_collection = db.get_collection("trade_logs")
market_data_log_collection = db.get_collection("market_data_log")

async def init_db():
    """Initialize database indexes and default settings."""
    try:
        # Test connection
        await client.admin.command('ping')
        print("✅ Pinged your deployment. You successfully connected to MongoDB!")
    except ConnectionFailure as e:
        print(f"❌ MongoDB connection failed: {e}")
        return

    # Create indexes for faster queries
    await users_collection.create_index("username", unique=True)
    await settings_collection.create_index("username", unique=True)
    await trade_logs_collection.create_index([("username", 1), ("timestamp", -1)])
    await market_data_log_collection.create_index("timestamp")

    # Initialize default settings for known users
    for user in ["samarth", "prajwal"]:
        default_settings = {
            "delta_threshold": 0.20,
            "vega_threshold": 0.10,
            "theta_threshold": 0.02,
            "gamma_threshold": 0.01,
            "consecutive_confirmations": 2
        }
        await settings_collection.update_one(
            {"username": user},
            {"$setOnInsert": {"username": user, **default_settings}},
            upsert=True
        )

async def store_tokens(username: str, access_token: str, refresh_token: str, expires_at: int):
    """Store or update OAuth tokens for a user."""
    await users_collection.update_one(
        {"username": username},
        {
            "$set": {
                "access_token": access_token,
                "refresh_token": refresh_token,
                "token_expires_at": expires_at,
                "updated_at": datetime.utcnow()
            },
            "$setOnInsert": {"username": username, "created_at": datetime.utcnow()}
        },
        upsert=True
    )

async def get_user_tokens(username: str) -> Optional[Dict]:
    """Get stored tokens for a user."""
    user_doc = await users_collection.find_one({"username": username})
    return user_doc

async def get_user_settings(username: str) -> Optional[Dict]:
    """Get user settings."""
    settings_doc = await settings_collection.find_one({"username": username})
    return settings_doc

async def update_user_settings(username: str, settings: Dict) -> Optional[Dict]:
    """Update user settings."""
    update_data = {
        "delta_threshold": settings.get("delta_threshold"),
        "vega_threshold": settings.get("vega_threshold"),
        "theta_threshold": settings.get("theta_threshold"),
        "gamma_threshold": settings.get("gamma_threshold"),
        "consecutive_confirmations": settings.get("consecutive_confirmations"),
    }
    # Filter out None values
    update_data = {k: v for k, v in update_data.items() if v is not None}

    result = await settings_collection.find_one_and_update(
        {"username": username},
        {"$set": update_data},
        return_document=True
    )
    return result

async def log_market_data(data: dict):
    """Logs a snapshot of market data to the database for ML training."""
    if not data or 'timestamp' not in data:
        return

    log_entry = {
        "timestamp": datetime.fromisoformat(data.get('timestamp')),
        "underlying_price": data.get('underlying_price'),
        "atm_strike": data.get('atm_strike'),
        "aggregated_greeks": data.get('aggregated_greeks', {}),
        "signals": data.get('signals', [])
    }
    await market_data_log_collection.insert_one(log_entry)

async def log_signal(username: str, position: str, strike_price: float, strike_ltp: float,
               delta: float, vega: float, theta: float, gamma: float, raw_chain: dict):
    """Log a detected signal."""
    log_entry = {
        "timestamp": datetime.utcnow(),
        "username": username,
        "detected_position": position,
        "strike_price": strike_price,
        "strike_ltp": strike_ltp,
        "delta": delta,
        "vega": vega,
        "theta": theta,
        "gamma": gamma,
        "raw_option_chain": json.dumps(raw_chain) # Storing as JSON string
    }
    await trade_logs_collection.insert_one(log_entry)

async def get_trade_logs(username: str, limit: int = 100) -> List[Dict]:
    """Get trade logs for a user."""
    cursor = trade_logs_collection.find({"username": username}).sort("timestamp", -1).limit(limit)
    logs = await cursor.to_list(length=limit)
    
    # Process logs to handle BSON/JSON conversion
    for log in logs:
        log["_id"] = str(log["_id"]) # Convert ObjectId to string
        if "raw_option_chain" in log and isinstance(log["raw_option_chain"], str):
            try:
                log["raw_option_chain"] = json.loads(log["raw_option_chain"])
            except json.JSONDecodeError:
                log["raw_option_chain"] = {"error": "Failed to decode JSON"}
    return logs

async def clear_user_tokens(username: str):
    """Clear tokens for a user on logout."""
    await users_collection.update_one(
        {"username": username},
        {"$set": {
            "access_token": None,
            "refresh_token": None,
            "token_expires_at": None
        }}
    )
