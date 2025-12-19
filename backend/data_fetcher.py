import httpx
import asyncio
from typing import Optional, Dict, List
from datetime import datetime, timedelta, timezone
from database import get_user_settings, get_user_tokens, log_signal, db
from calc import find_atm_strike
from auth import refresh_access_token
from greek_signals import detect_signals
from utils import aggregate_greeks_atm_otm
import json


def get_tuesday_expiry() -> str:
    """
    Get the next/current Tuesday expiry date in YYYY-MM-DD format
    If today is Tuesday before market close (3:30 PM IST), returns today
    Otherwise returns next Tuesday
    """
    now_utc = datetime.now(timezone.utc)
    market_close_utc_hour = 10 # 3:30 PM IST is 10:00 AM UTC
    
    # Monday is 0, Tuesday is 1
    days_until_tuesday = (1 - now_utc.weekday() + 7) % 7
    
    if days_until_tuesday == 0:
        # If it's Tuesday, check if we are past market close time
        if now_utc.hour >= market_close_utc_hour:
            expiry_date = now_utc + timedelta(days=7) # Get next week's Tuesday
        else:
            expiry_date = now_utc # Use today
    else:
        expiry_date = now_utc + timedelta(days=days_until_tuesday)
    
    return expiry_date.strftime("%Y-%m-%d")

# Global state
latest_data: Optional[Dict] = None
raw_option_chain: Optional[Dict] = None
baseline_greeks: Optional[Dict] = None # NEW: To store baseline greeks for the day
polling_active = False
should_poll = False  # Flag to control whether polling should actually fetch data
from ws_manager import manager # Import the shared manager instance
# Upstox API endpoints
UPSTOX_BASE_URL = "https://api.upstox.com/v2"
UPSTOX_OPTION_CHAIN_URL = f"{UPSTOX_BASE_URL}/option/chain"


async def fetch_option_chain(username: str) -> Optional[Dict]:
    """Fetch option chain data from Upstox API"""
    tokens = await get_user_tokens(username)
    if not tokens:
        print(f"No tokens found for user: {username}")
        return None
    
    # Check token expiration
    import time
    access_token = tokens.get("access_token")
    
    if not access_token or tokens.get("token_expires_at", 0) <= time.time():
        print(f"Token expired for user: {username}")
        new_access_token = await refresh_access_token(username)
        if not new_access_token:
            print(f"❌ Failed to refresh token for {username}. User needs to log in again.")
            return None
        access_token = new_access_token
    
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json"
    }
    
    # Upstox option chain endpoint - GET /option/chain
    # Required parameters: instrument_key and expiry_date
    
    # Instrument key for NIFTY50
    instrument_key = "NSE_INDEX|Nifty 50"
    
    # Get Tuesday expiry date
    expiry_date = get_tuesday_expiry()
    
    params = {
        "instrument_key": instrument_key,
        "expiry_date": expiry_date
    }
    
    # print(f"📊 Fetching option chain - Instrument: {instrument_key}, Expiry: {expiry_date}")
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                UPSTOX_OPTION_CHAIN_URL,
                headers=headers,
                params=params
            )
            
            if response.status_code != 200:
                print(f"API Error: {response.status_code} - {response.text}")
                return None
            
            result = response.json()
            
            # Check if status is success
            if result.get("status") != "success":
                print(f"API returned error status: {result}")
                return None
            
            # Add expiry_date to the result so it's available for normalization
            result["_expiry_date"] = expiry_date
            
            return result
    
    except Exception as e:
        print(f"Error fetching option chain: {e}")
        import traceback
        traceback.print_exc()
        return None
    
    # TODO: Uncomment and configure when you have the correct endpoint
    # instrument_key = "NSE_INDEX|Nifty 50"  # This needs to be the actual instrument key format
    # 
    # try:
    #     async with httpx.AsyncClient(timeout=10.0) as client:
    #         response = await client.get(
    #             UPSTOX_OPTION_CHAIN_URL,
    #             headers=headers,
    #             params={"instrument_key": instrument_key}
    #         )
    #         
    #         if response.status_code != 200:
    #             print(f"API Error: {response.status_code} - {response.text}")
    #             return None
    #         
    #         return response.json()
    # 
    # except Exception as e:
    #     print(f"Error fetching option chain: {e}")
    #     return None


def normalize_option_chain(upstox_data: Dict) -> Dict:
    """Normalize Upstox API response to our data model"""
    try:
        # print(f"🛰️ Normalizing option chain data...")
        
        if upstox_data.get("status") != "success":
            print(f"Invalid response status: {upstox_data.get('status')}")
            return None
        
        data_array = upstox_data.get("data", [])
        if not data_array:
            print("No data in response")
            return None
        
        # Extract underlying price from first item (all should have same underlying)
        underlying_price = data_array[0].get("underlying_spot_price", 0)
        
        if underlying_price == 0:
            print("Could not extract underlying price")
            return None
        
        # Convert Upstox format to our format
        options = []
        for item in data_array:
            strike_price = item.get("strike_price", 0)
            
            # Process Call option
            if "call_options" in item and item["call_options"]:
                call_data = item["call_options"]
                call_greeks = call_data.get("option_greeks", {})
                call_market = call_data.get("market_data", {})
                
                options.append({
                    "strike": strike_price,
                    "type": "CE",
                    "delta": call_greeks.get("delta", 0),
                    "vega": call_greeks.get("vega", 0),
                    "theta": call_greeks.get("theta", 0),
                    "gamma": call_greeks.get("gamma", 0),
                    "oi": call_market.get("oi", 0),
                    "ltp": call_market.get("ltp", 0),
                    "volume": call_market.get("volume", 0),  # Add this line
                    "iv": call_greeks.get("iv", 0)  # Implied volatility
                })
            
            # Process Put option
            if "put_options" in item and item["put_options"]:
                put_data = item["put_options"]
                put_greeks = put_data.get("option_greeks", {})
                put_market = put_data.get("market_data", {})
                
                options.append({
                    "strike": strike_price,
                    "type": "PE",
                    "delta": put_greeks.get("delta", 0),
                    "vega": put_greeks.get("vega", 0),
                    "theta": put_greeks.get("theta", 0),
                    "gamma": put_greeks.get("gamma", 0),
                    "oi": put_market.get("oi", 0),
                    "ltp": put_market.get("ltp", 0),
                    "volume": put_market.get("volume", 0),  # Add this line
                    "iv": put_greeks.get("iv", 0)  # Implied volatility
                })
        
        if not options:
            print("No options found in response")
            return None
        
        # Find ATM strike
        atm_strike = find_atm_strike(underlying_price, options)
        
        # Use expiry_date from fetch (stored in _expiry_date) or calculate it
        expiry_date = upstox_data.get("_expiry_date") or get_tuesday_expiry()
        
        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "underlying_price": underlying_price,
            "atm_strike": atm_strike,
            "expiry_date": expiry_date,
            "options": options
        }
    
    except Exception as e:
        print(f"Error normalizing option chain: {e}")
        import traceback
        traceback.print_exc()
        return None

def calculate_change_from_baseline(current_greeks: Dict, baseline: Dict) -> Dict:
    """NEW: Calculate the change between current and baseline greeks."""
    # Initialize with zeros to ensure structure exists for the signal detector
    change = {
        "call": {"delta": 0, "vega": 0, "theta": 0, "gamma": 0},
        "put": {"delta": 0, "vega": 0, "theta": 0, "gamma": 0}
    }
    
    if not baseline or not current_greeks:
        return change
    
    for side in ["call", "put"]:
        for greek in ["delta", "vega", "theta", "gamma"]:
            change[side][greek] = current_greeks.get(side, {}).get(greek, 0) - baseline.get(side, {}).get(greek, 0)
    return change

async def get_daily_baseline(username: str, date_str: str) -> Optional[Dict]:
    """Fetches the baseline for a specific user and date from the database."""
    baseline_doc = await db.daily_baselines.find_one({"username": username, "date": date_str})
    if baseline_doc:
        print(f"💾 Found existing baseline in DB for {username} on {date_str}")
        return baseline_doc.get("baseline_data")
    return None

async def save_daily_baseline(username: str, date_str: str, baseline_data: Dict):
    """Saves or updates the baseline for a specific user and date in the database."""
    print(f"💾 Saving baseline to DB for {username} on {date_str}")
    await db.daily_baselines.update_one(
        {"username": username, "date": date_str},
        {"$set": {"baseline_data": baseline_data}},
        upsert=True
    )

async def clear_daily_baseline(username: str, date_str: str):
    """Clears the baseline for a specific user and date from the database."""
    global baseline_greeks
    baseline_greeks = None # Clear in-memory baseline
    result = await db.daily_baselines.delete_one({"username": username, "date": date_str})
    if result.deleted_count > 0:
        print(f"🗑️ Cleared baseline from DB for {username} on {date_str}")

async def polling_worker():
    """Background worker that polls Upstox API every 5 seconds"""
    global latest_data, raw_option_chain, polling_active, should_poll, baseline_greeks
    
    polling_active = True
    current_user = None
    # State for consecutive signal confirmations, managed within the single polling task
    # This is robust against multi-worker deployments.
    signal_confirmation_state: Dict[str, Dict[str, int]] = {}
    
    print("Polling worker started. Operating autonomously during market hours (09:15 - 15:30 IST).")
    
    # Main polling loop - wait for explicit enable via login
    while polling_active:
        # Time Check: 09:15 to 15:30 IST
        now_utc = datetime.now(timezone.utc)
        now_ist = now_utc + timedelta(hours=5, minutes=30)
        
        # Check for weekends (Saturday=5, Sunday=6)
        if now_ist.weekday() >= 5:
            if current_user:
                print(f"📅 Weekend ({now_ist.strftime('%A')}). Stopping polling.")
                current_user = None
                latest_data = None
            await asyncio.sleep(3600) # Check every hour on weekends to save resources
            continue

        current_time = now_ist.time()
        start_time = datetime.strptime("09:15", "%H:%M").time()
        end_time = datetime.strptime("15:30", "%H:%M").time()

        if not (start_time <= current_time <= end_time):
            # Outside market hours
            if current_user:
                print(f"🕒 Market closed ({current_time.strftime('%H:%M')}). Stopping polling.")
                current_user = None # Reset user session
                latest_data = None
            await asyncio.sleep(60) # Check every minute
            continue
        
        # Find authenticated user (first available)
        found_user = None
        for user in ["samarth", "prajwal"]:
            tokens = await get_user_tokens(user)
            # Check if token exists. We allow expired tokens here because fetch_option_chain
            # has built-in logic to refresh them.
            if tokens and tokens.get("access_token"):
                found_user = user
                break
        
        if not found_user:
            # No authenticated user found - reset and wait
            if current_user:
                print(f"⚠️  No authenticated user available. Stopping polling...")
                current_user = None
                # Disable polling when user logs out
                # should_poll = False # Let logout handle this
            await asyncio.sleep(5)
            continue
        
        # We have an authenticated user and polling is enabled
        if found_user != current_user:
            current_user = found_user
            print(f"✓ Authenticated user found: {current_user}")
            print(f"Starting polling for {current_user}...")
            # Immediately set a placeholder message so the frontend knows the user is authenticated
            # This prevents the redirect loop on the frontend.
            latest_data = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "aggregated_greeks": None,
                "baseline_greeks": None,
                "change_from_baseline": None,
                "signals": [],
                "option_count": 0,
                "options": [],
                "underlying_price": None,
                "atm_strike": None,
                "message": f"Authenticated as {current_user}. Waiting for first data poll..."
            }

        
        try:
            # On first poll for a user, try to load baseline from DB
            if baseline_greeks is None:
                today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
                db_baseline = await get_daily_baseline(current_user, today_str)
                if db_baseline:
                    baseline_greeks = db_baseline

            # Fetch option chain
            upstox_data = await fetch_option_chain(current_user)
            
            if upstox_data:
                # Store raw data
                raw_option_chain = upstox_data
                
                # Normalize data
                normalized_data = normalize_option_chain(upstox_data)
                
                if not normalized_data:
                    print("⚠️  Failed to normalize option chain data")
                    await asyncio.sleep(5)
                    continue
                
                if not normalized_data.get("options"):
                    print(f"⚠️  No options found in normalized data. Keys: {list(normalized_data.keys())}")
                    await asyncio.sleep(5)
                    continue
                
                # We have valid normalized data with options
                try:
                    # NEW: Use the updated aggregation logic (ATM + 10 OTM)
                    aggregated = aggregate_greeks_atm_otm(normalized_data)

                    # Set baseline if it's not already set (from DB or previous poll)
                    # Also capture if it's invalid (e.g., all zeros)
                    is_baseline_invalid = not baseline_greeks or baseline_greeks.get("call", {}).get("delta") == 0
                    if is_baseline_invalid and aggregated:
                        baseline_greeks = aggregated
                        print("📈 Baseline greeks captured for the day.")
                        today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
                        await save_daily_baseline(current_user, today_str, baseline_greeks)
                    
                    # NEW: Calculate change from baseline BEFORE detecting signals
                    change_from_baseline = calculate_change_from_baseline(aggregated, baseline_greeks)

                    # Detect signals - PASS CHANGE INSTEAD OF ABSOLUTE VALUES
                    # This ensures we are detecting the "Drift" (Signature) and not just static values.
                    signals = await detect_signals(normalized_data, change_from_baseline, current_user, signal_confirmation_state)

                    # Post-process signals for logging based on confirmation count
                    settings = await get_user_settings(current_user)
                    required_confirmations = settings.get("consecutive_confirmations", 2) if settings else 2

                    for signal in signals:
                        if signal.get("all_matched"):
                            position = signal["position"]
                            # Check if we've reached required confirmations
                            if signal_confirmation_state.get(current_user, {}).get(position, 0) >= required_confirmations:
                                # Log signal - use ATM strike for the detected position
                                strike_price = normalized_data["atm_strike"]
                                strike_ltp = 0
                                option_type = "CE" if "Call" in position else "PE"
                                
                                # Find the LTP for ATM strike of the detected type
                                for opt in normalized_data["options"]:
                                    if opt["type"] == option_type and opt["strike"] == strike_price:
                                        strike_ltp = opt.get("ltp", 0)
                                        break
                                await log_signal(
                                    username=current_user,
                                    position=position,
                                    strike_price=strike_price,
                                    strike_ltp=strike_ltp,
                                    delta=signal["delta"]["value"],
                                    vega=signal["vega"]["value"],
                                    theta=signal["theta"]["value"],
                                    gamma=signal["gamma"]["value"],
                                    raw_chain=normalized_data
                                )
                                # Reset counter after logging
                                signal_confirmation_state[current_user][position] = 0
                    
                    # Combine all data
                    latest_data = {
                        "timestamp": normalized_data["timestamp"],
                        "underlying_price": normalized_data["underlying_price"],
                        "atm_strike": normalized_data["atm_strike"],
                        "expiry_date": normalized_data.get("expiry_date"),
                        "aggregated_greeks": aggregated,
                        "baseline_greeks": baseline_greeks,
                        "change_from_baseline": change_from_baseline,
                        "signals": signals,
                        "option_count": len(normalized_data.get("options", [])),
                        "options": normalized_data.get("options", []) # Add full options list for OptionChain page
                    }
                    
                    # Broadcast to WebSocket clients
                    if manager:
                        await manager.broadcast(latest_data)
                        # Import here to avoid circular dependency
                        from database import log_market_data
                        # Log the data to the database for ML training
                        await log_market_data(latest_data)
                except Exception as e:
                    print(f"⚠️  Error processing data: {e}")
        
        except asyncio.CancelledError:
            break
        except Exception as e:
            print(f"Error in polling worker: {str(e)}")
            import traceback
            traceback.print_exc()
        finally:
            # Wait 5 seconds before next poll, even if an error occurred
            await asyncio.sleep(5)
    
    polling_active = False
    should_poll = False
    print("Polling worker stopped")


async def start_polling():
    """Start the polling worker"""
    await polling_worker() # Start the worker


async def stop_polling():
    """Stop the polling worker"""
    global polling_active, should_poll, latest_data, baseline_greeks
    polling_active = False
    should_poll = False
    print("🛑 Polling stopped")


def enable_polling():
    """Enable polling - called after successful login"""
    global should_poll
    global latest_data
    latest_data = None
    reset_baseline_greeks() # Clear in-memory baseline to force a reload from DB on next poll
    should_poll = True
    print("✅ Polling enabled - will start fetching data")


def disable_polling():
    """Disable polling - called on logout"""
    global should_poll, latest_data
    should_poll = False
    latest_data = None  # Clear the data when polling is disabled
    reset_baseline_greeks() # Clear in-memory baseline on logout
    print("🛑 Polling disabled - will stop fetching data")


def reset_baseline_greeks():
    """Manually reset the baseline greeks. The worker will clear it from the DB."""
    global baseline_greeks
    # This function is now simpler. It just clears the in-memory version.
    # The polling worker will see it's None, capture a new one, and save it.
    # The new API endpoint will handle DB clearing directly for immediate effect.
    baseline_greeks = None
    print("🔄 In-memory baseline greeks have been reset. A new baseline will be captured on the next poll.")


def get_latest_data() -> Optional[Dict]:
    """Get the latest fetched data"""
    return latest_data


def get_raw_option_chain() -> Optional[Dict]:
    """Get raw option chain data"""
    return raw_option_chain

async def get_current_authenticated_user() -> Optional[str]:
    """
    Checks which user has a valid, active token and returns their username.
    """
    import time
    for user in ["samarth", "prajwal"]:
        tokens = await get_user_tokens(user)
        if tokens:
            # Check if token exists, is not null, and is not expired
            if tokens.get("access_token") and tokens.get("token_expires_at", 0) > time.time():
                return user
    return None
