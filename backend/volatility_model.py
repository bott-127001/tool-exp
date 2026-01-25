"""
Volatility-Permission Model
Calculates RV(current), RV(open-normalized), IV(ATM), IV-VWAP
and determines market states: CONTRACTION, TRANSITION, EXPANSION
"""
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta, timezone
import statistics


def calculate_rv_current(price_series_15min: Optional[List[float]]) -> Optional[float]:
    """
    Calculate RV(current) - 15-minute displacement.
    
    RV_current = abs(Price_last - Price_first) over the 15-minute window.
    """
    if not price_series_15min or len(price_series_15min) < 2:
        return None

    # Use the most recent 15-min window as RV_current
    # Price_last_tick is the last element, Price_first_tick is the first element of the 15min series
    return abs(price_series_15min[-1] - price_series_15min[0])


def calculate_rv_open_normalized(current_price: float, open_price: float, 
                                  market_open_time: datetime, current_time: datetime) -> Optional[float]:
    """
    Calculate RV(open-normalized) - day's average movement speed
    1. RV_open(t) = |Price_t - OpenPrice|
    2. RV_open_norm(t) = RV_open(t) / Number of 15-min windows elapsed
    """
    if open_price is None or open_price == 0:
        return None
    
    # Calculate time difference in minutes
    time_diff = current_time - market_open_time
    minutes_elapsed = time_diff.total_seconds() / 60
    
    # Calculate number of 15-minute windows elapsed
    windows_elapsed = max(1, minutes_elapsed / 15)  # At least 1 to avoid division by zero
    
    # Calculate RV from open
    rv_open = abs(current_price - open_price)
    
    # Normalize by time
    rv_open_norm = rv_open / windows_elapsed
    
    return rv_open_norm


def calculate_rv_median(
    full_day_price_history: List[Dict],
    current_time: datetime
) -> Optional[float]:
    """
    Calculate RV_median as the median of the last 4 completed 15-min windows.
    
    Why RV_median?
    It provides a robust, short-term smoothing baseline aligned with 45-min holding trades,
    filtering out transient spikes while adapting faster than a full-day average.
    
    Windows considered (rolling back from current time):
    1. [t-15m, t] (Current developing window)
    2. [t-30m, t-15m]
    3. [t-45m, t-30m]
    4. [t-60m, t-45m]
    """
    if not full_day_price_history:
        return None
        
    rv_values = []
    
    # Ensure current_time is timezone aware if history is (to avoid comparison errors)
    if full_day_price_history and full_day_price_history[0]["timestamp"].tzinfo is not None and current_time.tzinfo is None:
        current_time = current_time.replace(tzinfo=timezone.utc)

    for i in range(4):
        end_time = current_time - timedelta(minutes=15 * i)
        start_time = current_time - timedelta(minutes=15 * (i + 1))
        
        # Collect prices in this window
        window_prices = [
            p["price"] for p in full_day_price_history 
            if start_time <= p["timestamp"] <= end_time
        ]
        
        if len(window_prices) >= 2:
            # Displacement: abs(Last - First)
            rv_values.append(abs(window_prices[-1] - window_prices[0]))
            
    if not rv_values:
        return None
        
    return statistics.median(rv_values)

def _get_atm_cluster_options(options: List[Dict], atm_strike: float) -> List[Dict]:
    """
    Build the strict ATM IV cluster:
      - ATM CE
      - ATM PE
      - ATM-1 strike CE
      - ATM-1 strike PE
      - ATM+1 strike CE
      - ATM+1 strike PE

    We infer ATM±1 by walking the sorted unique strikes around the given ATM strike.
    """
    if not options:
        return []

    # Collect unique strikes and sort them
    strikes = sorted({opt.get("strike") for opt in options if opt.get("strike") is not None})
    if not strikes:
        return []

    # Find the exact ATM strike index
    try:
        atm_index = strikes.index(atm_strike)
    except ValueError:
        # If the provided ATM strike isn't in the list, find the nearest strike
        closest_strike = min(strikes, key=lambda s: abs(s - atm_strike))
        atm_index = strikes.index(closest_strike)

    cluster_strikes: List[float] = []
    # ATM-1
    if atm_index - 1 >= 0:
        cluster_strikes.append(strikes[atm_index - 1])
    # ATM
    cluster_strikes.append(strikes[atm_index])
    # ATM+1
    if atm_index + 1 < len(strikes):
        cluster_strikes.append(strikes[atm_index + 1])

    cluster_strike_set = set(cluster_strikes)

    # Filter options for these strikes and for CE/PE only
    cluster_options: List[Dict] = []
    for opt in options:
        strike = opt.get("strike")
        opt_type = opt.get("type")
        if strike in cluster_strike_set and opt_type in ("CE", "PE"):
            cluster_options.append(opt)

    return cluster_options


def get_iv_cluster(options: List[Dict], atm_strike: float) -> Optional[float]:
    """
    Get IV (ATM-cluster) as the simple average IV of the strict 6-option cluster:
      ATM CE/PE and ATM±1 strike CE/PE.
    """
    cluster_options = _get_atm_cluster_options(options, atm_strike)
    if not cluster_options:
        return None

    iv_values = [
        opt.get("iv")
        for opt in cluster_options
        if opt.get("iv") is not None and opt.get("iv") > 0
    ]

    if not iv_values:
        return None

    return sum(iv_values) / len(iv_values)


def calculate_iv_vwap(options: List[Dict], atm_strike: float) -> Optional[float]:
    """
    Calculate IV-VWAP over the strict ATM IV cluster only.

    IV_VWAP(t) = Σ(IV_i × Volume_i) / Σ Volume_i
    """
    cluster_options = _get_atm_cluster_options(options, atm_strike)
    if not cluster_options:
        return None
    
    total_iv_volume = 0.0
    total_volume = 0.0
    
    for opt in cluster_options:
        iv = opt.get("iv", 0)
        volume = opt.get("volume", 0)
        
        if iv and iv > 0 and volume and volume > 0:
            total_iv_volume += iv * volume
            total_volume += volume
    
    if total_volume == 0:
        return None
    
    return total_iv_volume / total_volume


def determine_market_state(
    rv_ratio: Optional[float],
    rv_ratio_delta: Optional[float],
    iv_atm: Optional[float],
    iv_vwap: Optional[float],
    market_open_time: Optional[datetime] = None,
    current_time: Optional[datetime] = None,
    prev_state: str = "UNKNOWN",
    transition_minutes_guardrail: int = 30,
    rv_ratio_contraction_threshold: float = 0.8,
    rv_ratio_expansion_threshold: float = 1.5,
    min_rv_ratio_acceleration: float = 0.05,
) -> Tuple[str, Dict]:
    """
    Determine market state: CONTRACTION, TRANSITION, or EXPANSION
    
    State Stabilization Logic:
    1. IV Grey Zone: ±10% around IV_VWAP.
       - Expansion requires IV > IV_VWAP * 1.10
       - Non-Expansion (Transition/Contraction) requires IV < IV_VWAP * 0.90
    2. RV Ratio Grey Buffer: +0.2.
       - Transition requires RV_ratio > threshold + 0.2
       - Expansion requires RV_ratio > threshold + 0.2
    
    Guardrail: TRANSITION state is not allowed before X minutes from market open
    (default: 30 minutes)
    
    Returns:
        (state_name, state_info)
    """
    # If we don't have enough data, return unknown
    if rv_ratio is None or iv_atm is None or iv_vwap is None:
        return ("UNKNOWN", {
            "reason": "Insufficient data",
            "rv_ratio": rv_ratio,
            "iv_atm": iv_atm,
            "iv_vwap": iv_vwap
        })
    
    # Check if we're within the guardrail period (before X minutes from open)
    within_guardrail = False
    if market_open_time is not None and current_time is not None:
        time_since_open = current_time - market_open_time
        minutes_since_open = time_since_open.total_seconds() / 60
        within_guardrail = minutes_since_open < transition_minutes_guardrail
    
    # Define buffered thresholds for state changes
    iv_expansion_trigger = iv_vwap * 1.10
    iv_non_expansion_trigger = iv_vwap * 0.90
    
    rv_transition_trigger = rv_ratio_contraction_threshold + 0.2
    rv_expansion_trigger = rv_ratio_expansion_threshold + 0.2

    # 1. CONTRACTION (NO TRADE)
    # RV_ratio < threshold AND IV < 0.90 * VWAP (Strict low vol)
    if rv_ratio < rv_ratio_contraction_threshold and iv_atm < iv_non_expansion_trigger:
        return ("CONTRACTION", {
            "reason": f"RV_ratio < {rv_ratio_contraction_threshold} and IV < 90% VWAP (Low Volatility)",
            "action": "NO TRADE - No naked buying",
            "stabilization": "Strict condition met",
            "rv_ratio": rv_ratio,
            "iv_atm": iv_atm,
            "iv_vwap": iv_vwap
        })

    # 2. TRANSITION (ONLY VALID ENTRY ZONE)
    # RV_ratio > (threshold + 0.2) AND Accelerating AND IV < 0.90 * VWAP
    is_accelerating = False
    if rv_ratio_delta is not None:
        is_accelerating = rv_ratio_delta >= min_rv_ratio_acceleration

    # Note: We removed the upper bound check (<= expansion_threshold) here because
    # if RV is very high but IV is still LOW, it is a valid Transition (buying opportunity).
    if rv_ratio > rv_transition_trigger and is_accelerating and iv_atm < iv_non_expansion_trigger:
        if within_guardrail:
            # Guardrail: Force CONTRACTION if within guardrail period
            return ("CONTRACTION", {
                "reason": f"TRANSITION blocked by guardrail - less than {transition_minutes_guardrail} minutes from open",
                "action": "NO TRADE - Wait for guardrail period to pass",
                "stabilization": "Guardrail active",
                "rv_ratio": rv_ratio,
                "iv_atm": iv_atm,
                "iv_vwap": iv_vwap,
                "guardrail_active": True,
                "minutes_since_open": (current_time - market_open_time).total_seconds() / 60 if market_open_time and current_time else None
            })
        else:
            return ("TRANSITION", {
                "reason": f"RV_ratio > {rv_transition_trigger:.2f} (Buffered), Accelerating, IV < 90% VWAP",
                "action": "VALID ENTRY ZONE - Buy options here",
                "stabilization": "Strict condition met",
                "rv_ratio": rv_ratio,
                "rv_ratio_delta": rv_ratio_delta,
                "iv_atm": iv_atm,
                "iv_vwap": iv_vwap,
                "is_accelerating": True
            })
    
    # 3. EXPANSION (DO NOT ENTER FRESH)
    # RV_ratio > (threshold + 0.2) AND IV > 1.10 * VWAP
    if rv_ratio > rv_expansion_trigger and iv_atm > iv_expansion_trigger:
        return ("EXPANSION", {
            "reason": f"RV_ratio > {rv_expansion_trigger:.2f} (Buffered) and IV > 110% VWAP (Repriced)",
            "action": "DO NOT ENTER FRESH - Manage existing trades only",
            "stabilization": "Strict condition met",
            "rv_ratio": rv_ratio,
            "iv_atm": iv_atm,
            "iv_vwap": iv_vwap
        })
    
    # 4. GREY ZONE / FALLBACK
    # If we are here, current metrics do not strictly satisfy any new state condition.
    # Retain the previous state if it was valid.
    if prev_state in ["CONTRACTION", "TRANSITION", "EXPANSION"]:
        return (prev_state, {
            "reason": f"Grey Zone - Retaining previous state ({prev_state})",
            "action": "HOLD STATE - Metrics in buffer zone",
            "stabilization": "Grey Zone Active",
            "rv_ratio": rv_ratio,
            "iv_atm": iv_atm,
            "iv_vwap": iv_vwap
        })

    # Default fallback
    return ("UNKNOWN", {
        "reason": "Default state - conditions not met for Transition or Expansion",
        "action": "NO TRADE",
        "rv_ratio": rv_ratio,
        "iv_atm": iv_atm,
        "iv_vwap": iv_vwap
    })


def calculate_volatility_metrics(
    current_price: float,
    price_15min_ago: Optional[float],
    price_series_15min: Optional[List[float]],
    open_price: Optional[float],
    market_open_time: datetime,
    current_time: datetime,
    options: List[Dict],
    atm_strike: float,
    underlying_price: float,
    full_day_price_history: List[Dict],
    rv_ratio_prev: Optional[float] = None,
    prev_volatility_metrics: Optional[Dict] = None,
    rv_ratio_contraction_threshold: float = 0.8,
    rv_ratio_expansion_threshold: float = 1.5,
    min_rv_ratio_acceleration: float = 0.05,
) -> Dict:
    """
    Calculate all volatility metrics and determine market state
    
    Returns a dictionary with all calculated values and market state
    """
    # Calculate metrics
    rv_current = calculate_rv_current(price_series_15min)
    rv_open_norm = calculate_rv_open_normalized(current_price, open_price, market_open_time, current_time)
    rv_median = calculate_rv_median(full_day_price_history, current_time)
    
    rv_ratio = None
    rv_ratio_delta = None
    
    # Use RV_median as the denominator for short-term smoothing.
    # Fallback to RV_open_norm if median is unavailable or zero.
    denominator = rv_median if (rv_median is not None and rv_median > 0) else rv_open_norm

    if rv_current is not None and denominator is not None and denominator > 0:
        rv_ratio = rv_current / denominator
        if rv_ratio_prev is not None and rv_ratio_prev > 0:
            rv_ratio_delta = (rv_ratio / rv_ratio_prev) - 1
        
    iv_atm = get_iv_cluster(options, atm_strike)
    iv_vwap = calculate_iv_vwap(options, atm_strike)
    
    # Extract previous state info for stabilization
    prev_confirmed_state = "UNKNOWN"
    prev_pending_state = None
    prev_pending_start = None
    
    if prev_volatility_metrics:
        prev_confirmed_state = prev_volatility_metrics.get("market_state", "UNKNOWN")
        prev_pending_state = prev_volatility_metrics.get("pending_state")
        start_str = prev_volatility_metrics.get("pending_state_start_time")
        if start_str:
            try:
                prev_pending_start = datetime.fromisoformat(start_str)
            except (ValueError, TypeError):
                pass

    # Determine "Candidate" market state using Grey Zone logic
    candidate_state, candidate_info = determine_market_state(
        rv_ratio, rv_ratio_delta, iv_atm, iv_vwap, 
        market_open_time=market_open_time,
        current_time=current_time,
        prev_state=prev_confirmed_state,
        rv_ratio_contraction_threshold=rv_ratio_contraction_threshold,
        rv_ratio_expansion_threshold=rv_ratio_expansion_threshold,
        min_rv_ratio_acceleration=min_rv_ratio_acceleration
    )
    
    # Apply Debounce / Hold Rule (1-minute hold)
    final_state = prev_confirmed_state
    final_state_info = candidate_info
    
    pending_state = prev_pending_state
    pending_state_start_time = prev_pending_start
    
    if candidate_state == prev_confirmed_state:
        # Condition holds or is in grey zone retaining state -> Reset pending
        pending_state = None
        pending_state_start_time = None
        final_state = candidate_state
    else:
        # Candidate differs from confirmed
        if candidate_state == pending_state:
            # We are already pending this state, check duration
            if pending_state_start_time:
                duration = (current_time - pending_state_start_time).total_seconds()
                if duration >= 60:
                    # Confirmed!
                    final_state = candidate_state
                    pending_state = None
                    pending_state_start_time = None
                else:
                    # Keep waiting, retain old state
                    final_state = prev_confirmed_state
                    final_state_info["stabilization_status"] = f"Pending switch to {candidate_state} ({int(duration)}s/60s)"
        else:
            # New pending state detected
            pending_state = candidate_state
            pending_state_start_time = current_time
            final_state = prev_confirmed_state
            final_state_info["stabilization_status"] = f"New pending state: {candidate_state}"

    return {
        "rv_current": rv_current,
        "rv_open_norm": rv_open_norm,
        "rv_median": rv_median,
        "rv_ratio": rv_ratio,
        "rv_ratio_delta": rv_ratio_delta,
        "iv_atm": iv_atm,
        "iv_vwap": iv_vwap,
        "market_state": final_state,
        "state_info": final_state_info,
        "pending_state": pending_state,
        "pending_state_start_time": pending_state_start_time.isoformat() if pending_state_start_time else None,
        "current_price": current_price,
        "open_price": open_price,
        "price_15min_ago": price_15min_ago,
        "timestamp": current_time.isoformat()
    }
