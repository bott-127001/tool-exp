import httpx
import asyncio
from typing import Optional, Dict, List
from datetime import datetime, timedelta
from database import get_user_tokens, log_signal
from calc import find_atm_strike
from auth import refresh_access_token
from greek_signals import detect_signals
import json


def get_tuesday_expiry() -> str:
    """
    Get the next/current Tuesday expiry date in YYYY-MM-DD format
    If today is Tuesday before market close (3:30 PM IST), returns today
    Otherwise returns next Tuesday
    """
    today = datetime.now()
    
    # Calculate days until next Tuesday (Tuesday = 1 in weekday, Monday = 0)
    days_until_tuesday = (1 - today.weekday()) % 7
    
    # If today is Tuesday
    if days_until_tuesday == 0:
        # Check if before market close (3:30 PM IST = 10:00 AM UTC)
        # For simplicity, if it's Tuesday, use today's date
        # You can adjust this logic based on your needs
        expiry_date = today
    else:
        # Get next Tuesday
        expiry_date = today + timedelta(days=days_until_tuesday)
    
    return expiry_date.strftime("%Y-%m-%d")

# Global state
latest_data: Optional[Dict] = None
raw_option_chain: Optional[Dict] = None
baseline_greeks: Optional[Dict] = None # NEW: To store baseline greeks for the day
polling_active = False
should_poll = False  # Flag to control whether polling should actually fetch data
connection_manager = None

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
            "timestamp": datetime.now().isoformat(),
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

def aggregate_greeks_atm_otm(normalized_data: Dict) -> Dict:
    """
    NEW: Aggregate Greeks for ATM + 10 OTM strikes as per the new plan.
    """
    atm_strike = normalized_data.get("atm_strike")
    options = normalized_data.get("options", [])
    
    if not atm_strike or not options:
        return {"call": {}, "put": {}}

    # Sort strikes to easily find OTM
    all_strikes = sorted(list(set(opt['strike'] for opt in options)))
    
    try:
        atm_index = all_strikes.index(atm_strike)
    except ValueError:
        return {"call": {}, "put": {}} # ATM strike not in list

    # Define the 11 strikes for Calls (ATM and higher) and Puts (ATM and lower)
    call_strikes = set(all_strikes[atm_index : atm_index + 11])
    put_strikes = set(all_strikes[max(0, atm_index - 10) : atm_index + 1])

    call_greeks = {"delta": 0, "vega": 0, "theta": 0, "gamma": 0, "option_count": 0}
    put_greeks = {"delta": 0, "vega": 0, "theta": 0, "gamma": 0, "option_count": 0}

    for opt in options:
        if opt['type'] == 'CE' and opt['strike'] in call_strikes:
            call_greeks['delta'] += opt.get('delta', 0)
            call_greeks['vega'] += opt.get('vega', 0)
            call_greeks['theta'] += opt.get('theta', 0)
            call_greeks['gamma'] += opt.get('gamma', 0)
            call_greeks['option_count'] += 1
        elif opt['type'] == 'PE' and opt['strike'] in put_strikes:
            put_greeks['delta'] += opt.get('delta', 0)
            put_greeks['vega'] += opt.get('vega', 0)
            put_greeks['theta'] += opt.get('theta', 0)
            put_greeks['gamma'] += opt.get('gamma', 0)
            put_greeks['option_count'] += 1
            
    return {"call": call_greeks, "put": put_greeks}

def calculate_change_from_baseline(current_greeks: Dict, baseline: Dict) -> Dict:
    """NEW: Calculate the change between current and baseline greeks."""
    if not baseline:
        return {"call": {}, "put": {}} # No baseline to compare against
    
    change = {"call": {}, "put": {}}
    for side in ["call", "put"]:
        for greek in ["delta", "vega", "theta", "gamma"]:
            change[side][greek] = current_greeks[side].get(greek, 0) - baseline[side].get(greek, 0)
    return change

async def polling_worker(manager):
    """Background worker that polls Upstox API every 5 seconds"""
    global latest_data, raw_option_chain, polling_active, should_poll, baseline_greeks
    
    polling_active = True
    current_user = None
    # State for consecutive signal confirmations, managed within the single polling task
    # This is robust against multi-worker deployments.
    signal_confirmation_state: Dict[str, Dict[str, int]] = {}
    
    print("Polling worker started. Waiting for explicit login to start polling...")
    
    # Main polling loop - wait for explicit enable via login
    while polling_active:
        # Only poll if should_poll is True AND we have an authenticated user
        if not should_poll:
            # Polling disabled - wait and check again
            await asyncio.sleep(1)
            continue
        
        # Find authenticated user (first available)
        found_user = None
        for user in ["samarth", "prajwal"]:
            tokens = await get_user_tokens(user)
            if tokens:
                import time
                # Check if token exists and is not null
                if tokens.get("access_token") and tokens["token_expires_at"] > time.time():
                    found_user = user
                    break
        
        if not found_user:
            # No authenticated user found - reset and wait
            if current_user:
                print(f"⚠️  No authenticated user available. Stopping polling...")
                current_user = None
                # Disable polling when user logs out
                # should_poll = False # Let logout handle this
            await asyncio.sleep(2)
            continue
        
        # We have an authenticated user and polling is enabled
        if found_user != current_user:
            current_user = found_user
            print(f"✓ Authenticated user found: {current_user}")
            print(f"Starting polling for {current_user}...")
        
        try:
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

                    # NEW: Set baseline on the first successful fetch of the session
                    if baseline_greeks is None:
                        baseline_greeks = aggregated
                        print("📈 Baseline greeks captured for the day.")
                    
                    # Detect signals
                    signals = await detect_signals(normalized_data, aggregated, current_user, signal_confirmation_state)

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
                    
                    # NEW: Calculate change from baseline
                    change_from_baseline = calculate_change_from_baseline(aggregated, baseline_greeks)
                    
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
                        "option_count": len(normalized_data.get("options", []))
                    }
                    
                    # Broadcast to WebSocket clients
                    if manager:
                        await manager.broadcast(latest_data)

                        # Import here to avoid circular dependency
                        from database import log_market_data
                        # Log the data to the database for ML training
                        await log_market_data(latest_data)
                    else:
                        print(f"⚠️  No WebSocket manager available")
                except Exception as e:
                    print(f"⚠️  Error processing data: {e}")
            
            # Wait 5 seconds before next poll
            await asyncio.sleep(5)
        
        except asyncio.CancelledError:
            break
        except Exception as e:
            print(f"Error in polling worker: {str(e)}")
            import traceback
            traceback.print_exc()
            await asyncio.sleep(5)
    
    polling_active = False
    should_poll = False
    print("Polling worker stopped")


async def start_polling(manager):
    """Start the polling worker"""
    global connection_manager
    connection_manager = manager
    await polling_worker(manager)


async def stop_polling():
    """Stop the polling worker"""
    global polling_active, should_poll, latest_data, baseline_greeks
    polling_active = False
    should_poll = False
    print("🛑 Polling stopped")


def enable_polling():
    """Enable polling - called after successful login"""
    global should_poll
    # Reset data on new login to ensure no stale data is shown
    global latest_data, baseline_greeks
    latest_data = None
    baseline_greeks = None # Reset baseline for the new session
    should_poll = True
    print("✅ Polling enabled - will start fetching data")


def disable_polling():
    """Disable polling - called on logout"""
    global should_poll, latest_data, baseline_greeks
    should_poll = False
    latest_data = None  # Clear the data when polling is disabled
    baseline_greeks = None # Clear baseline on logout
    print("🛑 Polling disabled - will stop fetching data")


def get_latest_data() -> Optional[Dict]:
    """Get the latest fetched data"""
    return latest_data


def get_raw_option_chain() -> Optional[Dict]:
    """Get raw option chain data"""
    return raw_option_chain
