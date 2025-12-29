"""
Volatility-Permission Model
Calculates RV(current), RV(open-normalized), IV(ATM), IV-VWAP
and determines market states: CONTRACTION, TRANSITION, EXPANSION
"""
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta, timezone


def calculate_rv_current(current_price: float, price_15min_ago: Optional[float]) -> Optional[float]:
    """
    Calculate RV(current) - 15-minute realized volatility
    RV_current(t) = |Price_t - Price_{t-15min}|
    """
    if price_15min_ago is None:
        return None
    return abs(current_price - price_15min_ago)


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


def get_atm_iv(options: List[Dict], atm_strike: float, underlying_price: float) -> Optional[float]:
    """
    Get IV (ATM) - current implied volatility for ATM option
    Takes ATM (or nearest ITM) option IV from option chain
    """
    if not options:
        return None
    
    # Find ATM option (prefer ITM if available)
    atm_options = []
    for opt in options:
        if opt.get("strike") == atm_strike:
            atm_options.append(opt)
    
    if not atm_options:
        # Find nearest strike to ATM
        min_diff = float('inf')
        nearest_opt = None
        for opt in options:
            diff = abs(opt.get("strike", 0) - atm_strike)
            if diff < min_diff:
                min_diff = diff
                nearest_opt = opt
        
        if nearest_opt:
            return nearest_opt.get("iv")
        return None
    
    # Prefer ITM option if available
    # For calls: ITM means strike < underlying, for puts: strike > underlying
    # But we'll just take the first one with IV > 0
    for opt in atm_options:
        iv = opt.get("iv")
        if iv and iv > 0:
            return iv
    
    # If no IV found, return None
    return None


def calculate_iv_vwap(options: List[Dict]) -> Optional[float]:
    """
    Calculate IV-VWAP - fair volatility price for the day
    IV_VWAP(t) = Σ(IV_i * Volume_i) / Σ(Volume_i)
    """
    if not options:
        return None
    
    total_iv_volume = 0.0
    total_volume = 0.0
    
    for opt in options:
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
    rv_current = calculate_rv_current(current_price, price_15min_ago)
    rv_open_norm = calculate_rv_open_normalized(current_price, open_price, market_open_time, current_time)
    iv_atm = get_atm_iv(options, atm_strike, underlying_price)
    iv_vwap = calculate_iv_vwap(options)
    
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

