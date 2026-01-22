"""
Volatility-Permission Model
Calculates RV(current), RV(open-normalized), IV(ATM), IV-VWAP
and determines market states: CONTRACTION, TRANSITION, EXPANSION
"""
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta, timezone


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
    transition_minutes_guardrail: int = 30,
    rv_ratio_contraction_threshold: float = 0.8,
    rv_ratio_expansion_threshold: float = 1.5,
    min_rv_ratio_acceleration: float = 0.05,
) -> Tuple[str, Dict]:
    """
    Determine market state: CONTRACTION, TRANSITION, or EXPANSION
    
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
    
    # CONTRACTION (NO TRADE)
    # RV_ratio < threshold AND IV_cluster <= IV_VWAP
    if rv_ratio < rv_ratio_contraction_threshold and iv_atm <= iv_vwap:
        return ("CONTRACTION", {
            "reason": f"RV_ratio < {rv_ratio_contraction_threshold} (Low Volatility) and IV not repriced",
            "action": "NO TRADE - No naked buying",
            "rv_ratio": rv_ratio,
            "iv_atm": iv_atm,
            "iv_vwap": iv_vwap
        })
    
    # TRANSITION (ONLY VALID ENTRY ZONE)
    # threshold_low <= RV_ratio <= threshold_high
    # AND RV_ratio is increasing compared to previous interval
    # AND IV_cluster <= IV_VWAP
    is_accelerating = False
    if rv_ratio_delta is not None:
        is_accelerating = rv_ratio_delta >= min_rv_ratio_acceleration

    
    if rv_ratio_contraction_threshold <= rv_ratio <= rv_ratio_expansion_threshold and is_accelerating and iv_atm <= iv_vwap:
        if within_guardrail:
            # Guardrail: Force CONTRACTION if within guardrail period
            return ("CONTRACTION", {
                "reason": f"TRANSITION blocked by guardrail - less than {transition_minutes_guardrail} minutes from open",
                "action": "NO TRADE - Wait for guardrail period to pass",
                "rv_ratio": rv_ratio,
                "iv_atm": iv_atm,
                "iv_vwap": iv_vwap,
                "guardrail_active": True,
                "minutes_since_open": (current_time - market_open_time).total_seconds() / 60 if market_open_time and current_time else None
            })
        else:
            return ("TRANSITION", {
                "reason": f"RV_ratio in transition zone ({rv_ratio_contraction_threshold}-{rv_ratio_expansion_threshold}) and accelerating (delta >= {min_rv_ratio_acceleration}), IV stable",
                "action": "VALID ENTRY ZONE - Buy options here",
                "rv_ratio": rv_ratio,
                "rv_ratio_delta": rv_ratio_delta,
                "iv_atm": iv_atm,
                "iv_vwap": iv_vwap,
                "is_accelerating": True
            })
    
    # EXPANSION (DO NOT ENTER FRESH)
    # RV_ratio > threshold AND IV_cluster > IV_VWAP
    if rv_ratio > rv_ratio_expansion_threshold and iv_atm > iv_vwap:
        return ("EXPANSION", {
            "reason": f"RV_ratio > {rv_ratio_expansion_threshold} (High Volatility) and IV repriced",
            "action": "DO NOT ENTER FRESH - Manage existing trades only",
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
    rv_current_prev: Optional[float] = None,
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
    
    rv_ratio = None
    rv_ratio_delta = None
    if rv_current is not None and rv_open_norm is not None and rv_open_norm > 0:
        rv_ratio = rv_current / rv_open_norm
        if rv_current_prev is not None and rv_current_prev > 0:
            rv_ratio_delta = (rv_current / rv_current_prev) - 1
        
    iv_atm = get_iv_cluster(options, atm_strike)
    iv_vwap = calculate_iv_vwap(options, atm_strike)
    
    # Determine market state
    state_name, state_info = determine_market_state(
        rv_ratio, rv_ratio_delta, iv_atm, iv_vwap, 
        market_open_time=market_open_time,
        current_time=current_time,
        rv_ratio_contraction_threshold=rv_ratio_contraction_threshold,
        rv_ratio_expansion_threshold=rv_ratio_expansion_threshold,
        min_rv_ratio_acceleration=min_rv_ratio_acceleration
    )
    
    return {
        "rv_current": rv_current,
        "rv_open_norm": rv_open_norm,
        "rv_ratio": rv_ratio,
        "rv_ratio_delta": rv_ratio_delta,
        "iv_atm": iv_atm,
        "iv_vwap": iv_vwap,
        "market_state": state_name,
        "state_info": state_info,
        "current_price": current_price,
        "open_price": open_price,
        "price_15min_ago": price_15min_ago,
        "timestamp": current_time.isoformat()
    }
