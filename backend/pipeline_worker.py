"""
Pipeline Worker - Refactored polling logic with discrete stages

This module contains the main polling worker that executes data fetching
and calculations in a controlled, sequential manner using the pipeline architecture.
"""

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, List, Any

from pipeline import pipeline, PipelineStage
from ws_manager import manager
from database import (
    get_user_tokens, get_user_settings, update_user_settings,
    log_market_data, db
)


async def find_authenticated_user() -> Optional[str]:
    """
    Stage 0: Find an authenticated user with valid tokens from today.
    Returns username if found, None otherwise.
    """
    now_utc = datetime.now(timezone.utc)
    now_ist = now_utc + timedelta(hours=5, minutes=30)
    today_str = now_ist.strftime("%Y-%m-%d")
    
    for user in ["samarth", "prajwal"]:
        tokens = await get_user_tokens(user)
        if not tokens or not tokens.get("access_token"):
            continue
        
        updated_at = tokens.get("updated_at")
        if updated_at:
            try:
                if isinstance(updated_at, datetime):
                    if updated_at.tzinfo is not None:
                        updated_utc = updated_at.astimezone(timezone.utc)
                    else:
                        updated_utc = updated_at.replace(tzinfo=timezone.utc)
                    updated_ist = updated_utc + timedelta(hours=5, minutes=30)
                else:
                    updated_dt = datetime.fromisoformat(str(updated_at).replace('Z', '+00:00'))
                    if updated_dt.tzinfo is None:
                        updated_dt = updated_dt.replace(tzinfo=timezone.utc)
                    updated_utc = updated_dt.astimezone(timezone.utc)
                    updated_ist = updated_utc + timedelta(hours=5, minutes=30)
                
                token_date_str = updated_ist.strftime("%Y-%m-%d")
                if token_date_str == today_str:
                    return user
            except Exception as e:
                print(f"⚠️ Error checking token date for {user}: {e}")
                continue
    
    return None


async def fetch_stage(username: str) -> Optional[Dict]:
    """
    Stage 1: Fetch option chain data from Upstox API.
    Returns raw API response or None on failure.
    """
    from data_fetcher import fetch_option_chain
    
    try:
        upstox_data = await asyncio.wait_for(
            fetch_option_chain(username),
            timeout=15.0
        )
        return upstox_data
    except asyncio.TimeoutError:
        print(f"⚠️ API call timeout for {username}")
        return None
    except Exception as e:
        print(f"⚠️ Fetch error for {username}: {e}")
        return None


async def normalize_stage(raw_data: Dict) -> Optional[Dict]:
    """
    Stage 2: Normalize the raw Upstox API response to our data model.
    Returns normalized data or None on failure.
    """
    from data_fetcher import normalize_option_chain
    
    try:
        normalized = normalize_option_chain(raw_data)
        if not normalized:
            print("⚠️ Failed to normalize option chain data")
            return None
        if not normalized.get("options"):
            print(f"⚠️ No options found in normalized data")
            return None
        return normalized
    except Exception as e:
        print(f"⚠️ Normalization error: {e}")
        return None


async def aggregate_stage(normalized_data: Dict) -> Optional[Dict]:
    """
    Stage 3: Aggregate Greeks for Call and Put sides (ATM + 10 OTM).
    Returns aggregated Greeks dict.
    """
    from utils import aggregate_greeks_atm_otm
    
    try:
        aggregated = aggregate_greeks_atm_otm(normalized_data)
        return aggregated
    except Exception as e:
        print(f"⚠️ Aggregation error: {e}")
        return None


async def baseline_stage(username: str, aggregated: Dict) -> tuple:
    """
    Stage 4: Handle baseline Greeks - load from DB or capture new.
    Returns (baseline_greeks, change_from_baseline).
    """
    from data_fetcher import (
        get_daily_baseline, save_daily_baseline, 
        calculate_change_from_baseline
    )
    
    state = pipeline.state
    
    if state.baseline_greeks is None:
        today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        db_baseline = await get_daily_baseline(username, today_str)
        if db_baseline:
            state.baseline_greeks = db_baseline
    
    is_baseline_invalid = (
        not state.baseline_greeks or 
        state.baseline_greeks.get("call", {}).get("delta") == 0
    )
    
    if is_baseline_invalid and aggregated:
        state.baseline_greeks = aggregated
        print("📈 Baseline greeks captured for the day.")
        today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        await save_daily_baseline(username, today_str, state.baseline_greeks)
    
    change_from_baseline = calculate_change_from_baseline(
        aggregated, state.baseline_greeks if state.baseline_greeks else {}
    )
    
    return state.baseline_greeks, change_from_baseline


async def fetch_supplementary_data_stage(username: str, settings: Dict) -> Dict:
    """
    Stage 5: Fetch supplementary data (previous day OHLC, open candle).
    Updates settings with fetched data.
    Returns updated settings.
    """
    from data_fetcher import (
        fetch_and_store_previous_day_data,
        fetch_current_day_open_candle
    )
    
    state = pipeline.state
    now_utc = datetime.now(timezone.utc)
    now_ist = now_utc + timedelta(hours=5, minutes=30)
    today_str = now_ist.strftime("%Y-%m-%d")
    
    last_fetched_date = state.prev_day_stats_fetched_for.get(username)
    if last_fetched_date != today_str:
        try:
            ohlc = await fetch_and_store_previous_day_data(username)
            if ohlc:
                state.prev_day_stats_fetched_for[username] = today_str
                settings = await get_user_settings(username) or {}
        except Exception as e:
            print(f"⚠️ Error fetching previous-day data: {e}")
    
    last_open_candle_date = state.current_day_open_candle_fetched_for.get(username)
    if last_open_candle_date != today_str:
        try:
            await asyncio.sleep(1)
            
            instrument_key = "NSE_INDEX|Nifty 50"
            candle_open_price = await fetch_current_day_open_candle(
                username, instrument_key
            )
            
            if candle_open_price is not None:
                state.current_day_open_candle_fetched_for[username] = today_str
                state.open_price_from_candle = candle_open_price
                if state.open_price != candle_open_price:
                    state.open_price = candle_open_price
                    print(f"🔄 Updated day's open price to candle open: {state.open_price}")
        except Exception as e:
            print(f"⚠️ Error fetching open candle: {e}")
    
    return settings


async def volatility_stage(
    normalized_data: Dict,
    settings: Dict,
    current_time: datetime
) -> Optional[Dict]:
    """
    Stage 6: Calculate volatility metrics (RV, IV, market state).
    Returns volatility metrics dict.
    """
    from volatility_model import calculate_volatility_metrics
    
    state = pipeline.state
    
    if state.open_price is None or state.market_open_time is None:
        print("⚠️ Skipping volatility: open_price or market_open_time not set")
        return None
    
    current_price = normalized_data["underlying_price"]
    price_15min_ago = pipeline.get_price_15min_ago(current_time)
    price_series_15min = [p.price for p in state.price_history]
    
    prev_volatility_data = (
        state.latest_data.get("volatility_metrics") 
        if state.latest_data else None
    )
    rv_ratio_prev = prev_volatility_data.get("rv_ratio") if prev_volatility_data else None
    
    try:
        volatility_metrics = calculate_volatility_metrics(
            current_price=current_price,
            price_15min_ago=price_15min_ago,
            price_series_15min=price_series_15min,
            open_price=state.open_price,
            market_open_time=state.market_open_time,
            current_time=current_time,
            options=normalized_data["options"],
            atm_strike=normalized_data["atm_strike"],
            underlying_price=current_price,
            full_day_price_history=pipeline.get_full_day_prices_as_dicts(),
            rv_ratio_prev=rv_ratio_prev,
            prev_volatility_metrics=prev_volatility_data,
            rv_ratio_contraction_threshold=settings.get("vol_rv_ratio_contraction_threshold", 0.8),
            rv_ratio_expansion_threshold=settings.get("vol_rv_ratio_expansion_threshold", 1.5),
            min_rv_ratio_acceleration=settings.get("vol_min_rv_ratio_acceleration", 0.05),
        )
        return volatility_metrics
    except Exception as e:
        print(f"⚠️ Volatility calculation error: {e}")
        import traceback
        traceback.print_exc()
        return None


async def direction_stage(
    settings: Dict,
    current_time: datetime
) -> Optional[Dict]:
    """
    Stage 7: Calculate direction & asymmetry metrics.
    Returns direction metrics dict.
    """
    from direction_model import calculate_direction_metrics
    
    state = pipeline.state
    
    if state.open_price is None or state.market_open_time is None:
        print("⚠️ Skipping direction: open_price or market_open_time not set")
        return None
    
    try:
        direction_metrics = calculate_direction_metrics(
            price_history=pipeline.get_full_day_prices_as_dicts(),
            market_open_time=state.market_open_time,
            current_time=current_time,
            settings=settings,
            open_price=state.open_price,
        )
        return direction_metrics
    except Exception as e:
        print(f"⚠️ Direction calculation error: {e}")
        import traceback
        traceback.print_exc()
        return None


async def signals_stage(
    normalized_data: Dict,
    change_from_baseline: Dict,
    username: str
) -> List[Dict]:
    """
    Stage 8: Detect Greek signature signals.
    Returns list of signal detection results.
    """
    from greek_signals import detect_signals
    
    state = pipeline.state
    
    try:
        signals = await detect_signals(
            normalized_data,
            change_from_baseline,
            username,
            state.signal_confirmation_state
        )
        return signals
    except Exception as e:
        print(f"⚠️ Signal detection error: {e}")
        return []


async def broadcast_stage(data: Dict):
    """
    Stage 9: Broadcast data to all connected WebSocket clients.
    """
    state = pipeline.state
    
    try:
        if manager:
            await manager.broadcast(data)
            
            if state.data_sequence % 10 == 0:
                await manager.cleanup_stale_connections(max_age_seconds=300)
    except Exception as e:
        print(f"⚠️ Broadcast error: {e}")


async def log_stage(data: Dict):
    """
    Stage 10: Log market data to database for ML training.
    """
    try:
        await log_market_data(data)
    except Exception as e:
        print(f"⚠️ Log error: {e}")


async def run_pipeline_cycle(username: str) -> bool:
    """
    Execute one complete pipeline cycle with all stages in sequence.
    Returns True if successful, False otherwise.
    
    This function MUST be called while holding the pipeline lock.
    """
    state = pipeline.state
    
    state.current_stage = PipelineStage.FETCHING
    raw_data = await fetch_stage(username)
    if not raw_data:
        return False
    
    state.raw_option_chain = raw_data
    
    state.current_stage = PipelineStage.NORMALIZING
    normalized_data = await normalize_stage(raw_data)
    if not normalized_data:
        return False
    
    timestamp_str = normalized_data["timestamp"]
    if timestamp_str.endswith('Z'):
        timestamp_str = timestamp_str.replace('Z', '+00:00')
    try:
        current_time = datetime.fromisoformat(timestamp_str)
        if current_time.tzinfo is None:
            current_time = current_time.replace(tzinfo=timezone.utc)
    except (ValueError, AttributeError):
        current_time = datetime.now(timezone.utc)
    
    current_price = normalized_data["underlying_price"]
    pipeline.update_price_history(current_price, current_time)
    
    state.current_stage = PipelineStage.AGGREGATING
    aggregated = await aggregate_stage(normalized_data)
    if not aggregated:
        return False
    
    state.current_stage = PipelineStage.CALCULATING_BASELINE
    baseline_greeks, change_from_baseline = await baseline_stage(username, aggregated)
    
    settings = await get_user_settings(username) or {}
    
    state.current_stage = PipelineStage.CALCULATING_VOLATILITY
    settings = await fetch_supplementary_data_stage(username, settings)
    
    if state.open_price is None or state.market_open_time is None:
        print("⚠️ Skipping metrics: open_price or market_open_time not yet available")
        return False
    
    volatility_metrics = await volatility_stage(normalized_data, settings, current_time)
    
    state.current_stage = PipelineStage.CALCULATING_DIRECTION
    direction_metrics = await direction_stage(settings, current_time)
    
    state.current_stage = PipelineStage.DETECTING_SIGNALS
    signals = await signals_stage(normalized_data, change_from_baseline, username)
    
    state.data_sequence += 1
    state.last_successful_poll = datetime.now(timezone.utc)
    state.stall_warning_sent = False
    
    latest_data = {
        "_sequence": state.data_sequence,
        "_poll_timestamp": state.last_successful_poll.isoformat(),
        "timestamp": normalized_data["timestamp"],
        "underlying_price": normalized_data["underlying_price"],
        "atm_strike": normalized_data["atm_strike"],
        "expiry_date": normalized_data.get("expiry_date"),
        "aggregated_greeks": aggregated,
        "baseline_greeks": baseline_greeks,
        "change_from_baseline": change_from_baseline,
        "signals": signals,
        "option_count": len(normalized_data.get("options", [])),
        "options": normalized_data.get("options", []),
        "volatility_metrics": volatility_metrics,
        "direction_metrics": direction_metrics,
    }
    
    state.latest_data = latest_data
    
    state.current_stage = PipelineStage.BROADCASTING
    await broadcast_stage(latest_data)
    
    state.current_stage = PipelineStage.LOGGING
    await log_stage(latest_data)
    
    state.current_stage = PipelineStage.COMPLETE
    return True


async def polling_worker():
    """
    Main polling worker that runs the pipeline every 5 seconds.
    Uses proper locking to prevent race conditions.
    """
    state = pipeline.state
    state.polling_active = True
    
    print("Pipeline worker started. Operating during market hours (09:15 - 15:30 IST).")
    
    while state.polling_active:
        poll_start_time = datetime.now(timezone.utc)
        
        now_utc = datetime.now(timezone.utc)
        now_ist = now_utc + timedelta(hours=5, minutes=30)
        
        if now_ist.weekday() >= 5:
            if state.current_user:
                print(f"📅 Weekend ({now_ist.strftime('%A')}). Stopping polling.")
                state.current_user = None
                state.latest_data = None
            await asyncio.sleep(3600)
            continue
        
        if not pipeline.is_market_hours():
            if state.current_user:
                print(f"🕒 Market closed ({now_ist.time().strftime('%H:%M')}). Stopping polling.")
                state.current_user = None
                state.latest_data = None
            await asyncio.sleep(60)
            continue
        
        found_user = await find_authenticated_user()
        
        if not found_user:
            if state.current_user:
                print("⚠️ No authenticated user with today's tokens. Waiting for login...")
                state.current_user = None
                state.latest_data = None
            await asyncio.sleep(5)
            continue
        
        if not state.should_poll:
            await asyncio.sleep(2)
            continue
        
        if found_user != state.current_user:
            state.current_user = found_user
            print(f"✓ Authenticated user found: {state.current_user}")
            print(f"Starting polling for {state.current_user}...")
            
            state.latest_data = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "aggregated_greeks": None,
                "baseline_greeks": None,
                "change_from_baseline": None,
                "signals": [],
                "option_count": 0,
                "options": [],
                "underlying_price": None,
                "atm_strike": None,
                "message": f"Authenticated as {state.current_user}. Waiting for first data poll..."
            }
        
        lock_acquired = await pipeline.acquire_lock(timeout=10.0)
        if not lock_acquired:
            print("⚠️ Could not acquire pipeline lock, skipping cycle")
            await asyncio.sleep(5)
            continue
        
        try:
            if not state.current_user:
                print("⚠️ No authenticated user, skipping cycle")
                continue
            success = await run_pipeline_cycle(state.current_user)
            if not success:
                if state.last_successful_poll:
                    time_since_success = (
                        datetime.now(timezone.utc) - state.last_successful_poll
                    ).total_seconds()
                    if time_since_success > 30 and not state.stall_warning_sent:
                        print(f"⚠️ STALL DETECTED: No successful poll in {time_since_success:.1f}s")
                        state.stall_warning_sent = True
        except asyncio.CancelledError:
            break
        except Exception as e:
            print(f"Error in pipeline cycle: {str(e)}")
            import traceback
            traceback.print_exc()
        finally:
            pipeline.release_lock()
            
            poll_duration = (datetime.now(timezone.utc) - poll_start_time).total_seconds()
            sleep_time = max(0, 5.0 - poll_duration)
            if sleep_time > 0:
                await asyncio.sleep(sleep_time)
    
    state.polling_active = False
    state.should_poll = False
    print("Pipeline worker stopped")


async def start_polling():
    """Start the polling worker with singleton guard."""
    if pipeline._polling_task is not None and not pipeline._polling_task.done():
        print("⚠️ Polling worker already running, skipping duplicate start")
        return
    pipeline._polling_task = asyncio.create_task(polling_worker())


async def stop_polling():
    """Stop the polling worker with proper task cancellation."""
    state = pipeline.state
    state.polling_active = False
    state.should_poll = False
    
    if pipeline._polling_task is not None and not pipeline._polling_task.done():
        pipeline._polling_task.cancel()
        try:
            await pipeline._polling_task
        except asyncio.CancelledError:
            pass
    pipeline._polling_task = None
    print("🛑 Pipeline polling stopped")


def enable_polling():
    """Enable polling - called after successful login."""
    state = pipeline.state
    state.latest_data = None
    state.baseline_greeks = None
    state.current_day_open_candle_fetched_for.clear()
    state.prev_day_stats_fetched_for.clear()
    state.should_poll = True
    print("✅ Polling enabled - will start fetching data with today's fresh tokens")


def disable_polling():
    """Disable polling - called on logout."""
    state = pipeline.state
    state.should_poll = False
    state.latest_data = None
    state.baseline_greeks = None
    print("🛑 Polling disabled - will stop fetching data")


def get_latest_data() -> Optional[Dict]:
    """Get the latest data from the pipeline state."""
    return pipeline.state.latest_data


def get_current_user() -> Optional[str]:
    """Get the currently authenticated user."""
    return pipeline.state.current_user


async def reset_baseline():
    """Reset the baseline greeks with proper locking."""
    lock_acquired = await pipeline.acquire_lock(timeout=5.0)
    if not lock_acquired:
        raise Exception("Could not acquire pipeline lock for baseline reset")
    
    try:
        pipeline.state.baseline_greeks = None
        pipeline.state.price_history = []
        pipeline.state.full_day_price_history = []
    finally:
        pipeline.release_lock()
