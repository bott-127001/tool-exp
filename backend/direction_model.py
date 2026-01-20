"""
Direction & Asymmetry Model (Price-Based)

Calculates:
1) Opening Location + Gap Acceptance
2) Range Extension Asymmetry (REA)
3) Delta Efficiency (DE)

And derives a daily directional state:
- DIRECTIONAL_BULL
- DIRECTIONAL_BEAR
- NEUTRAL
"""
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta, timezone


def calculate_gap_and_acceptance(
    open_price: Optional[float],
    previous_close: Optional[float],
    previous_day_range: Optional[float],
    intraday_prices: List[Dict],
    session_start: datetime,
    gap_acceptance_threshold: float = 0.65,
    acceptance_neutral_threshold: float = 0.5,
) -> Dict:
    """
    Opening Location + Gap Acceptance

    Gap         = Open - PreviousClose
    Gap_Pct     = |Gap| / PreviousDayRange

    Acceptance_Ratio = % of 5-min closes in gap direction after first 30 min
    
    NEW IMPLEMENTATION:
    - Filters prices to only include those after first 30 minutes from session_start
    - Groups prices into 5-minute candles
    - For each 5-minute candle, uses the close price (last price in that window)
    - Counts how many 5-minute closes are in the gap direction
    - Calculates the percentage
    
    This approach is less noisy than tick-based and less laggy than candle-close based.

    NOTE: For now, this implementation assumes previous_close and previous_day_range
    are not yet available from the DB, so it focuses on Acceptance_Ratio and treats
    Gap_Pct as None. Once previous-day stats are wired in, these can be populated.
    """
    result = {
        "gap": None,
        "gap_pct": None,
        "acceptance_ratio": None,
        "bias": "NEUTRAL",  # BULLISH / BEARISH / NEUTRAL
        "needs_prev_day_input": False,
        "missing_prev_fields": [],
        "stale_prev_day_data": False,
    }

    if open_price is None or not intraday_prices:
        return result

    # Compute gap only if we have previous day data
    if previous_close is not None and previous_day_range and previous_day_range > 0:
        gap = open_price - previous_close
        gap_pct = abs(gap) / previous_day_range
        result["gap"] = gap
        result["gap_pct"] = gap_pct
        print(f"✅ Gap calculation: open={open_price}, prev_close={previous_close}, gap={gap:.2f}, gap_pct={gap_pct:.4f}")
    else:
        gap = 0.0  # Treat as non-gap day for now
        result["needs_prev_day_input"] = True
        missing = []
        if previous_close is None:
            missing.append("previous_close")
        if previous_day_range is None or previous_day_range <= 0:
            missing.append("previous_day_range")
        result["missing_prev_fields"] = missing
        print(f"⚠️  Gap calculation skipped: previous_close={previous_close}, previous_day_range={previous_day_range}")

    # Acceptance: % of 5-min closes in gap direction after first 30 min
    # NEW IMPLEMENTATION:
    # 1. Filter prices to only include those after first 30 minutes from session_start
    # 2. Group prices into 5-minute candles
    # 3. For each 5-minute candle, get the close price (last price in that window)
    # 4. Count how many 5-minute closes are in the gap direction
    # 5. Calculate the percentage
    
    # Filter prices after first 30 minutes
    guardrail_end_time = session_start + timedelta(minutes=30)
    prices_after_30min = [
        p for p in intraday_prices 
        if p["timestamp"] > guardrail_end_time
    ]
    
    if not prices_after_30min:
        # Not enough data after 30 minutes
        result["acceptance_ratio"] = None
        return result
    
    # Group prices into 5-minute candles
    # Each candle represents a 5-minute window
    candle_closes = []  # List of close prices for each 5-minute candle
    
    # Start from guardrail_end_time and create 5-minute windows
    current_window_start = guardrail_end_time
    window_prices = []
    
    for price_entry in prices_after_30min:
        timestamp = price_entry["timestamp"]
        price = price_entry["price"]
        
        # Check if this price belongs to the current 5-minute window
        if timestamp < current_window_start + timedelta(minutes=5):
            window_prices.append(price)
        else:
            # Close the current window and start a new one
            if window_prices:
                # Close price is the last price in the window
                candle_closes.append(window_prices[-1])
            
            # Start new window
            # Find the start of the 5-minute window this price belongs to
            minutes_since_guardrail = (timestamp - guardrail_end_time).total_seconds() / 60
            window_number = int(minutes_since_guardrail / 5)
            current_window_start = guardrail_end_time + timedelta(minutes=window_number * 5)
            window_prices = [price]
    
    # Don't forget the last window
    if window_prices:
        candle_closes.append(window_prices[-1])
    
    # Calculate acceptance ratio: % of 5-min closes in gap direction
    if not candle_closes:
        result["acceptance_ratio"] = None
        return result
    
    closes_in_gap_direction = 0
    total_closes = len(candle_closes)
    
    for close_price in candle_closes:
        if gap > 0:
            # Gap UP → close above open
            if close_price >= open_price:
                closes_in_gap_direction += 1
        elif gap < 0:
            # Gap DOWN → close below open
            if close_price <= open_price:
                closes_in_gap_direction += 1
        else:
            # No meaningful gap → treat as close above open
            if close_price >= open_price:
                closes_in_gap_direction += 1
    
    acceptance_ratio = closes_in_gap_direction / total_closes if total_closes > 0 else None
    result["acceptance_ratio"] = acceptance_ratio
    
    if acceptance_ratio is not None:

        # Bias logic from spec (configurable thresholds)
        if gap > 0 and acceptance_ratio > gap_acceptance_threshold:
            result["bias"] = "BULLISH"
        elif gap < 0 and acceptance_ratio > gap_acceptance_threshold:
            result["bias"] = "BEARISH"
        elif acceptance_ratio < acceptance_neutral_threshold:
            result["bias"] = "NEUTRAL"
        else:
            result["bias"] = "NEUTRAL"

    return result


def calculate_rea(
    intraday_prices: List[Dict],
    session_start: datetime,
) -> Optional[Dict]:
    """
    Range Extension Asymmetry (REA)

    Define Initial Balance (IB) as first X minutes of the session.
    NOTE: Currently set to 45 minutes (9:15 AM to 10:00 AM IST).

    IB_high, IB_low
    IB_range = IB_high - IB_low

    RE_up   = DayHigh - IB_high
    RE_down = IB_low - DayLow

    REA = (RE_up - RE_down) / IB_range
    """
    if not intraday_prices:
        return None

    if session_start is None:
        return None

    # Ensure session_start is timezone-aware (assume UTC if not)
    if session_start.tzinfo is None:
        session_start = session_start.replace(tzinfo=timezone.utc)

    # Always use the first price timestamp as the effective session start
    # IB window is calculated from when the first fetch occurs, not from market open time
    first_price_ts = None
    for p in intraday_prices:
        ts = p.get("timestamp")
        if ts:
            if isinstance(ts, str):
                try:
                    ts = datetime.fromisoformat(ts.replace('Z', '+00:00'))
                except:
                    continue
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            if first_price_ts is None or ts < first_price_ts:
                first_price_ts = ts
    
    # Always use first_price_ts as effective start (when first fetch occurred)
    # Only fall back to session_start if we can't find any price timestamps
    if first_price_ts:
        effective_start = first_price_ts
    else:
        effective_start = session_start

    # Split IB vs rest of day based on X minutes from session_start
    # Changed to 45 minutes for production
    ib_minutes = 45  # Initial Balance period: 45 minutes
    ib_end = effective_start + timedelta(minutes=ib_minutes)
    
    # Ensure all timestamps are timezone-aware for comparison
    ib_prices = []
    all_prices = []
    
    for p in intraday_prices:
        price = p.get("price")
        if price is None:
            continue
        
        all_prices.append(price)
        
        price_timestamp = p.get("timestamp")
        if price_timestamp is None:
            continue
        
        # Ensure timestamp is timezone-aware
        if isinstance(price_timestamp, str):
            # Try to parse if it's a string
            try:
                price_timestamp = datetime.fromisoformat(price_timestamp.replace('Z', '+00:00'))
            except:
                continue
        
        if price_timestamp.tzinfo is None:
            price_timestamp = price_timestamp.replace(tzinfo=timezone.utc)
        
        # Compare timestamps (both should be timezone-aware now)
        try:
            if price_timestamp <= ib_end:
                ib_prices.append(price)
        except (TypeError, ValueError) as e:
            # If comparison fails, skip
            continue

    if len(all_prices) == 0:
        return None

    if len(ib_prices) == 0:
        return None

    if len(all_prices) == 0:
        return None

    ib_high = max(ib_prices)
    ib_low = min(ib_prices)
    ib_range = ib_high - ib_low

    if ib_range <= 0:
        return None

    # Calculate current day high and low from ALL prices collected so far
    # This represents the day's high/low up to the current moment (not just IB window)
    day_high = max(all_prices)
    day_low = min(all_prices)
    
    # Check if we have prices outside the IB window
    # If we only have IB window data, we can't calculate meaningful RE Up/Down yet
    has_data_outside_ib = len(all_prices) > len(ib_prices)

    # Calculate RE Up and RE Down
    # RE Up = Day High - IB High (how much price extended above IB)
    # RE Down = IB Low - Day Low (how much price extended below IB)
    re_up = max(0.0, day_high - ib_high)
    re_down = max(0.0, ib_low - day_low)
    
    # Calculate REA only if we have data outside IB window
    # If we only have IB data, return None for RE Up/Down/REA (frontend will show N/A)
    if not has_data_outside_ib:
        return {
            "ib_high": ib_high,
            "ib_low": ib_low,
            "ib_range": ib_range,
            "day_high": day_high,
            "day_low": day_low,
            "re_up": None,  # Show N/A until we have data outside IB
            "re_down": None,  # Show N/A until we have data outside IB
            "rea": None,  # Show N/A until we have data outside IB
        }
    
    # Calculate REA when we have data outside IB window
    if ib_range > 0:
        rea = (re_up - re_down) / ib_range
    else:
        rea = 0.0

    return {
        "ib_high": ib_high,
        "ib_low": ib_low,
        "ib_range": ib_range,
        "day_high": day_high,
        "day_low": day_low,
        "re_up": re_up,
        "re_down": re_down,
        "rea": rea,
    }


def calculate_delta_efficiency(
    intraday_prices: List[Dict],
    open_price: Optional[float],
    close_price: Optional[float],
) -> Optional[float]:
    """
    Delta Efficiency (DE)

    r_i = Price_i - Price_{i-1}

    DE = |Close - Open| / Σ |r_i|
    """
    if open_price is None or close_price is None or len(intraday_prices) < 2:
        return None

    # Ensure prices in time order
    prices = [p["price"] for p in intraday_prices]
    denom = 0.0
    prev = prices[0]
    for price in prices[1:]:
        denom += abs(price - prev)
        prev = price

    if denom <= 0:
        return None

    de = abs(close_price - open_price) / denom
    return de


def determine_directional_state(
    opening_bias: str,
    rea_value: Optional[float],
    de_value: Optional[float],
    rea_bull_threshold: float = 0.3,
    rea_bear_threshold: float = -0.3,
    rea_neutral_abs_threshold: float = 0.3,
    de_directional_threshold: float = 0.5,
    de_neutral_threshold: float = 0.3,
) -> Tuple[str, Dict]:
    """
    Combine Opening Acceptance bias, REA, and DE into a directional state.

    States:
      - DIRECTIONAL_BULL
      - DIRECTIONAL_BEAR
      - NEUTRAL
    """
    info: Dict = {
        "opening_bias": opening_bias,
        "rea": rea_value,
        "de": de_value,
    }

    if rea_value is None or de_value is None:
        info["reason"] = "Insufficient data for REA or DE"
        return "NEUTRAL", info

    # Bullish directional day
    if opening_bias == "BULLISH" and rea_value > rea_bull_threshold and de_value > de_directional_threshold:
        info["reason"] = "Opening acceptance bullish, REA > bull threshold, DE > directional threshold"
        return "DIRECTIONAL_BULL", info

    # Bearish directional day
    if opening_bias == "BEARISH" and rea_value < rea_bear_threshold and de_value > de_directional_threshold:
        info["reason"] = "Opening acceptance bearish, REA < bear threshold, DE > directional threshold"
        return "DIRECTIONAL_BEAR", info

    # Neutral / no edge
    if de_value < de_neutral_threshold and abs(rea_value) < rea_neutral_abs_threshold:
        info["reason"] = "DE < neutral threshold and REA near zero → Neutral / no edge"
        return "NEUTRAL", info

    info["reason"] = "Mixed conditions → treat as NEUTRAL"
    return "NEUTRAL", info


def calculate_direction_metrics(
    price_history: List[Dict],
    market_open_time: Optional[datetime],
    current_time: Optional[datetime] = None,
    settings: Optional[Dict] = None,
) -> Dict:
    """
    High-level entry point to compute all Direction & Asymmetry metrics.

    NOTE: This relies only on intraday price history for the current day.
    Previous-day stats can be added later if available.
    """
    if not price_history or market_open_time is None:
        return {
            "opening": {
                "gap": None,
                "gap_pct": None,
                "acceptance_ratio": None,
                "bias": "NEUTRAL",
            },
            "rea": None,
            "de": None,
            "directional_state": "NEUTRAL",
            "directional_info": {"reason": "Insufficient intraday data"},
        }

    # Defaults for thresholds and optional previous-day inputs
    settings = settings or {}
    gap_acceptance_threshold = settings.get("dir_gap_acceptance_threshold", 0.65)
    acceptance_neutral_threshold = settings.get("dir_acceptance_neutral_threshold", 0.5)
    rea_bull_threshold = settings.get("dir_rea_bull_threshold", 0.3)
    rea_bear_threshold = settings.get("dir_rea_bear_threshold", -0.3)
    rea_neutral_abs_threshold = settings.get("dir_rea_neutral_abs_threshold", 0.3)
    de_directional_threshold = settings.get("dir_de_directional_threshold", 0.5)
    de_neutral_threshold = settings.get("dir_de_neutral_threshold", 0.3)

    # Optional previous-day inputs (can be provided from Direction & Asymmetry UI)
    previous_close = settings.get("prev_day_close")
    previous_day_range = settings.get("prev_day_range")
    previous_day_date_str = settings.get("prev_day_date")

    # Determine if previous-day inputs are stale
    # Data is considered valid if it's from the last trading day (handles holidays)
    # We allow data from up to 5 days ago (to account for weekends + holidays)
    stale_prev_day_data = False
    if current_time:
        today_date = current_time.date()
    elif market_open_time:
        today_date = market_open_time.date()
    else:
        today_date = None

    if today_date and previous_day_date_str:
        try:
            from datetime import date
            prev_day_date = date.fromisoformat(previous_day_date_str)
            
            # Calculate days difference
            days_diff = (today_date - prev_day_date).days
            
            # Data is valid if:
            # 1. It's from 1-5 days ago (handles holidays and weekends)
            # 2. The date is not a weekend (Saturday=5, Sunday=6)
            # 3. It's not in the future
            if days_diff < 1 or days_diff > 5:
                stale_prev_day_data = True
            elif prev_day_date.weekday() >= 5:  # Weekend
                stale_prev_day_data = True
            elif prev_day_date >= today_date:  # Future date
                stale_prev_day_data = True
        except Exception:
            stale_prev_day_data = True

    # If stale, ignore previous-day values for calculations
    if stale_prev_day_data:
        print(f"⚠️  Previous day data marked as stale: date={previous_day_date_str}, today={today_date}")
        previous_close = None
        previous_day_range = None
    elif previous_close is not None and previous_day_range is not None:
        print(f"✅ Using previous day data: date={previous_day_date_str}, close={previous_close}, range={previous_day_range}")

    # Ensure history is sorted by time
    history_sorted = sorted(price_history, key=lambda p: p["timestamp"])
    intraday_prices = history_sorted

    # Current open / close for today
    open_price = intraday_prices[0]["price"]
    close_price = intraday_prices[-1]["price"]

    opening = calculate_gap_and_acceptance(
        open_price=open_price,
        previous_close=previous_close,
        previous_day_range=previous_day_range,
        intraday_prices=intraday_prices,
        session_start=market_open_time,
        gap_acceptance_threshold=gap_acceptance_threshold,
        acceptance_neutral_threshold=acceptance_neutral_threshold,
    )

    # Surface stale flag to the frontend if applicable
    if stale_prev_day_data:
        opening["stale_prev_day_data"] = True

    rea_data = calculate_rea(
        intraday_prices=intraday_prices,
        session_start=market_open_time,
    )
    rea_value = rea_data["rea"] if rea_data else None

    de_value = calculate_delta_efficiency(
        intraday_prices=intraday_prices,
        open_price=open_price,
        close_price=close_price,
    )

    directional_state, directional_info = determine_directional_state(
        opening_bias=opening.get("bias", "NEUTRAL"),
        rea_value=rea_value,
        de_value=de_value,
        rea_bull_threshold=rea_bull_threshold,
        rea_bear_threshold=rea_bear_threshold,
        rea_neutral_abs_threshold=rea_neutral_abs_threshold,
        de_directional_threshold=de_directional_threshold,
        de_neutral_threshold=de_neutral_threshold,
    )

    return {
        "opening": opening,
        "rea": rea_data,
        "de": de_value,
        "directional_state": directional_state,
        "directional_info": directional_info,
    }


