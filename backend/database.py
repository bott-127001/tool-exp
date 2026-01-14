import json
import asyncio
from datetime import datetime
from typing import Optional, Dict, List
import os
try:
    import motor.motor_asyncio
    from pymongo import MongoClient
    from pymongo.server_api import ServerApi
    from pymongo.errors import ConnectionFailure
    import certifi
except ImportError:
    print("motor/pymongo not found. Please install with 'pip install motor pymongo'.")
    exit(1)

MONGO_URI = os.getenv("MONGO_URI")

# Only use SSL/TLS for MongoDB Atlas (cloud) connections, not for local MongoDB
# MongoDB Atlas connection strings contain "mongodb.net" or "mongodb+srv://"
if MONGO_URI and ("mongodb.net" in MONGO_URI or "mongodb+srv://" in MONGO_URI):
    # Cloud MongoDB (Atlas) - use SSL
    client = motor.motor_asyncio.AsyncIOMotorClient(MONGO_URI, tlsCAFile=certifi.where())
else:
    # Local MongoDB - no SSL
    if MONGO_URI:
        client = motor.motor_asyncio.AsyncIOMotorClient(MONGO_URI)
    else:
        # Fallback: try local MongoDB without connection string
        print("⚠️  MONGO_URI not set in .env file. Attempting to connect to local MongoDB...")
        client = motor.motor_asyncio.AsyncIOMotorClient("mongodb://localhost:27017/")

db = client.get_database("option_tool_db")

users_collection = db.get_collection("users")
settings_collection = db.get_collection("user_settings")
trade_logs_collection = db.get_collection("trade_logs")
market_data_log_collection = db.get_collection("market_data_log")
frontend_users_collection = db.get_collection("frontend_users")

async def init_db():
    """Initialize database indexes and default settings."""
    try:
        # Test connection with timeout
        await asyncio.wait_for(client.admin.command('ping'), timeout=5.0)
        print("✅ Pinged your deployment. You successfully connected to MongoDB!")
    except (ConnectionFailure, asyncio.TimeoutError, Exception) as e:
        print(f"❌ MongoDB connection failed: {e}")
        if not MONGO_URI:
            print("⚠️  Tip: Set MONGO_URI in your .env file with your MongoDB connection string")
            print("   For local MongoDB: MONGO_URI=mongodb://localhost:27017/")
            print("   For MongoDB Atlas: MONGO_URI=mongodb+srv://username:password@cluster.mongodb.net/")
        return

    # Create indexes for faster queries
    await users_collection.create_index("username", unique=True)
    await settings_collection.create_index("username", unique=True)
    await trade_logs_collection.create_index([("username", 1), ("timestamp", -1)])
    await market_data_log_collection.create_index("timestamp")
    await frontend_users_collection.create_index("username", unique=True)

    # Initialize frontend users
    await init_frontend_users()

    # Initialize default settings for known users
    for user in ["samarth", "prajwal"]:
        default_settings = {
            "delta_threshold": 0.20,
            "vega_threshold": 0.10,
            "theta_threshold": 0.02,
            "gamma_threshold": 0.01,
            "consecutive_confirmations": 2,
            # Volatility-permission thresholds
            "vol_expansion_rv_multiplier": 1.5,
            # Direction & Asymmetry thresholds
            "dir_gap_acceptance_threshold": 0.65,
            "dir_acceptance_neutral_threshold": 0.5,
            "dir_rea_bull_threshold": 0.3,
            "dir_rea_bear_threshold": -0.3,
            "dir_rea_neutral_abs_threshold": 0.3,
            "dir_de_directional_threshold": 0.5,
            "dir_de_neutral_threshold": 0.3,
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
                "updated_at": datetime.utcnow(),
                "last_login_success": True,  # Track successful login
                "last_login_failure": None   # Clear any previous failure
            },
            "$setOnInsert": {"username": username, "created_at": datetime.utcnow()}
        },
        upsert=True
    )


async def mark_login_failure(username: str, error_message: str = None):
    """Mark that login failed for a user on a specific date."""
    from datetime import timezone, timedelta
    now_utc = datetime.now(timezone.utc)
    now_ist = now_utc + timedelta(hours=5, minutes=30)
    today_str = now_ist.strftime("%Y-%m-%d")
    
    await users_collection.update_one(
        {"username": username},
        {
            "$set": {
                "last_login_failure": {
                    "date": today_str,
                    "timestamp": datetime.utcnow(),
                    "error": error_message
                },
                "last_login_success": False
            }
        }
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
    # Fields that should be updated (excluding prev_day fields which are handled separately)
    regular_fields = {
        "delta_threshold": settings.get("delta_threshold"),
        "vega_threshold": settings.get("vega_threshold"),
        "theta_threshold": settings.get("theta_threshold"),
        "gamma_threshold": settings.get("gamma_threshold"),
        "consecutive_confirmations": settings.get("consecutive_confirmations"),
        "vol_expansion_rv_multiplier": settings.get("vol_expansion_rv_multiplier"),
        "dir_gap_acceptance_threshold": settings.get("dir_gap_acceptance_threshold"),
        "dir_acceptance_neutral_threshold": settings.get("dir_acceptance_neutral_threshold"),
        "dir_rea_bull_threshold": settings.get("dir_rea_bull_threshold"),
        "dir_rea_bear_threshold": settings.get("dir_rea_bear_threshold"),
        "dir_rea_neutral_abs_threshold": settings.get("dir_rea_neutral_abs_threshold"),
        "dir_de_directional_threshold": settings.get("dir_de_directional_threshold"),
        "dir_de_neutral_threshold": settings.get("dir_de_neutral_threshold"),
    }
    # Filter out None values for regular fields
    update_data = {k: v for k, v in regular_fields.items() if v is not None}
    
    # Previous day inputs (for Opening Location & Gap Acceptance)
    # These should be included even if None (to allow clearing values)
    if "prev_day_close" in settings:
        update_data["prev_day_close"] = settings["prev_day_close"]
    if "prev_day_range" in settings:
        update_data["prev_day_range"] = settings["prev_day_range"]
    if "prev_day_date" in settings:
        update_data["prev_day_date"] = settings["prev_day_date"]

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


# Frontend user management (separate from Upstox OAuth)
async def create_frontend_user(username: str, password: str) -> bool:
    """
    Create a frontend user with hashed password.
    Returns True if created successfully, False if user already exists.
    """
    import bcrypt
    
    # Check if user already exists
    existing = await frontend_users_collection.find_one({"username": username})
    if existing:
        return False
    
    # Hash password
    password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    
    # Create user
    await frontend_users_collection.insert_one({
        "username": username,
        "password_hash": password_hash,
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow()
    })
    
    return True


async def verify_frontend_user(username: str, password: str) -> Optional[Dict]:
    """
    Verify frontend user credentials.
    Returns user dict if valid, None otherwise.
    """
    import bcrypt
    
    user = await frontend_users_collection.find_one({"username": username})
    if not user:
        return None
    
    # Verify password
    password_hash = user.get("password_hash")
    if not password_hash:
        return None
    
    if bcrypt.checkpw(password.encode('utf-8'), password_hash.encode('utf-8')):
        return {
            "username": user["username"],
            "created_at": user.get("created_at")
        }
    
    return None


async def get_frontend_user(username: str) -> Optional[Dict]:
    """Get frontend user by username."""
    user = await frontend_users_collection.find_one({"username": username})
    if user:
        return {
            "username": user["username"],
            "created_at": user.get("created_at")
        }
    return None


async def init_frontend_users():
    """
    Initialize default frontend users (samarth, prajwal) if they don't exist.
    Passwords should be set in environment variables.
    """
    import os
    import bcrypt
    
    for user in ["samarth", "prajwal"]:
        # Check if user exists
        existing = await frontend_users_collection.find_one({"username": user})
        if existing:
            continue
        
        # Get password from environment
        password_env_key = f"FRONTEND_{user.upper()}_PASSWORD"
        password = os.getenv(password_env_key)
        
        if not password:
            print(f"⚠️  Warning: {password_env_key} not set in .env. Frontend user '{user}' will not be created.")
            print(f"   Set {password_env_key}=your_password in .env to create this user.")
            continue
        
        # Hash and create user using upsert to avoid race conditions with multiple workers
        password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        result = await frontend_users_collection.update_one(
            {"username": user},
            {
                "$setOnInsert": {
                    "username": user,
                    "password_hash": password_hash,
                    "created_at": datetime.utcnow(),
                    "updated_at": datetime.utcnow()
                }
            },
            upsert=True
        )
        if result.upserted_id:
            print(f"✅ Created frontend user: {user}")
        # If user already exists, silently skip (no error)
