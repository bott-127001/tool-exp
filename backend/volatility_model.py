"""
Volatility-Permission Model
Calculates RV(current), RV(open-normalized), IV(ATM), IV-VWAP
and determines market states: CONTRACTION, TRANSITION, EXPANSION
"""
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta, timezone


def calculate_rv_current(price_series_15min: Optional[List[float]]) -> Optional[float]:
    """
    Calculate RV(current) - 15-minute realized volatility using micro-moves.

    Within the last 15 minutes of prices, RV_current(t) is defined as:

        RV_current(t) = Σ |Price_i − Price_(i−1)|

    This captures speed, activity, and urgency instead of just net drift.
    """
    if not price_series_15min or len(price_series_15min) < 2:
        return None

    rv = 0.0
    prev_price = price_series_15min[0]
    for price in price_series_15min[1:]:
        rv += abs(price - prev_price)
        prev_price = price

    return rv


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


def determine_market_state(rv_current: Optional[float], rv_open_norm: Optional[float],
                           rv_current_prev: Optional[float], iv_atm: Optional[float],
                           iv_vwap: Optional[float]) -> Tuple[str, Dict]:
    """
    Determine market state: CONTRACTION, TRANSITION, or EXPANSION
    
    Returns:
        (state_name, state_info)
    """
    # If we don't have enough data, return unknown
    if rv_current is None or rv_open_norm is None or iv_atm is None or iv_vwap is None:
        return ("UNKNOWN", {
            "reason": "Insufficient data",
            "rv_current": rv_current,
            "rv_open_norm": rv_open_norm,
            "iv_atm": iv_atm,
            "iv_vwap": iv_vwap
        })
    
    # CONTRACTION (NO TRADE)
    # Conditions:
    # - RV_current < RV_open_norm
    # - IV <= IV_VWAP
    if rv_current < rv_open_norm and iv_atm <= iv_vwap:
        return ("CONTRACTION", {
            "reason": "Market moving slower than average and IV not repriced",
            "action": "NO TRADE - No naked buying",
            "rv_current": rv_current,
            "rv_open_norm": rv_open_norm,
            "iv_atm": iv_atm,
            "iv_vwap": iv_vwap
        })
    
    # TRANSITION (ONLY VALID ENTRY ZONE)
    # Conditions:
    # - RV_current > RV_open_norm
    # - RV_current(t) > RV_current(t-1) (accelerating)
    # - IV <= IV_VWAP
    is_accelerating = rv_current_prev is not None and rv_current > rv_current_prev
    if rv_current > rv_open_norm and is_accelerating and iv_atm <= iv_vwap:
        return ("TRANSITION", {
            "reason": "Volatility accelerating but IV not repriced yet",
            "action": "VALID ENTRY ZONE - Buy options here",
            "rv_current": rv_current,
            "rv_open_norm": rv_open_norm,
            "iv_atm": iv_atm,
            "iv_vwap": iv_vwap,
            "is_accelerating": True
        })
    
    # EXPANSION (DO NOT ENTER FRESH)
    # Conditions:
    # - RV_current >> RV_open_norm (much greater)
    # - IV > IV_VWAP
    # Both conditions must be true (AND)
    if rv_current > rv_open_norm * 1.5 and iv_atm > iv_vwap:
        return ("EXPANSION", {
            "reason": "Volatility already released and options repriced",
            "action": "DO NOT ENTER FRESH - Manage existing trades only",
            "rv_current": rv_current,
            "rv_open_norm": rv_open_norm,
            "iv_atm": iv_atm,
            "iv_vwap": iv_vwap
        })
    
    # Default to TRANSITION if RV_current > RV_open_norm but not accelerating
    if rv_current > rv_open_norm:
        return ("TRANSITION", {
            "reason": "Volatility above average but not accelerating",
            "action": "Monitor - Entry may be valid if acceleration occurs",
            "rv_current": rv_current,
            "rv_open_norm": rv_open_norm,
            "iv_atm": iv_atm,
            "iv_vwap": iv_vwap,
            "is_accelerating": False
        })
    
    # Default fallback
    return ("CONTRACTION", {
        "reason": "Default state - market conditions unclear",
        "action": "NO TRADE",
        "rv_current": rv_current,
        "rv_open_norm": rv_open_norm,
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
    rv_current_prev: Optional[float] = None
) -> Dict:
    """
    Calculate all volatility metrics and determine market state
    
    Returns a dictionary with all calculated values and market state
    """
    # Calculate metrics
    rv_current = calculate_rv_current(price_series_15min)
    rv_open_norm = calculate_rv_open_normalized(current_price, open_price, market_open_time, current_time)
    iv_atm = get_iv_cluster(options, atm_strike)
    iv_vwap = calculate_iv_vwap(options, atm_strike)
    
    # Determine market state
    state_name, state_info = determine_market_state(
        rv_current, rv_open_norm, rv_current_prev, iv_atm, iv_vwap
    )
    
    return {
        "rv_current": rv_current,
        "rv_open_norm": rv_open_norm,
        "iv_atm": iv_atm,
        "iv_vwap": iv_vwap,
        "market_state": state_name,
        "state_info": state_info,
        "current_price": current_price,
        "open_price": open_price,
        "price_15min_ago": price_15min_ago,
        "timestamp": current_time.isoformat()
    }

