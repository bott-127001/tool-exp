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
from datetime import datetime, timedelta


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

    Acceptance_Ratio = Time_in_Gap_Direction / Total_Time

    NOTE: For now, this implementation assumes previous_close and previous_day_range
    are not yet available from the DB, so it focuses on Acceptance_Ratio and treats
    Gap_Pct as None. Once previous-day stats are wired in, these can be populated.
    """
    result = {
        "gap": None,
        "gap_pct": None,
        "acceptance_ratio": None,
        "bias": "NEUTRAL",  # BULLISH / BEARISH / NEUTRAL
    }

    if open_price is None or not intraday_prices:
        return result

    # Compute gap only if we have previous day data
    if previous_close is not None and previous_day_range and previous_day_range > 0:
        gap = open_price - previous_close
        gap_pct = abs(gap) / previous_day_range
        result["gap"] = gap
        result["gap_pct"] = gap_pct
    else:
        gap = 0.0  # Treat as non-gap day for now

    # Acceptance: time above/below open in the direction of the gap
    # intraday_prices: list of {"timestamp": dt, "price": float} sorted ascending
    total_seconds = 0.0
    time_in_gap_direction = 0.0

    for i in range(1, len(intraday_prices)):
        p_prev = intraday_prices[i - 1]
        p_cur = intraday_prices[i]
        dt = (p_cur["timestamp"] - p_prev["timestamp"]).total_seconds()
        if dt <= 0:
            continue
        total_seconds += dt

        price = p_prev["price"]
        if gap > 0:
            # Gap UP → time price stays above open
            if price >= open_price:
                time_in_gap_direction += dt
        elif gap < 0:
            # Gap DOWN → time price stays below open
            if price <= open_price:
                time_in_gap_direction += dt
        else:
            # No meaningful gap → treat direction as time above vs below open
            if price >= open_price:
                time_in_gap_direction += dt

    if total_seconds > 0:
        acceptance_ratio = time_in_gap_direction / total_seconds
        result["acceptance_ratio"] = acceptance_ratio

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

    Define Initial Balance (IB) as first 60 minutes of the session.

    IB_high, IB_low
    IB_range = IB_high - IB_low

    RE_up   = DayHigh - IB_high
    RE_down = IB_low - DayLow

    REA = (RE_up - RE_down) / IB_range
    """
    if not intraday_prices:
        return None

    # Split IB vs rest of day based on 60 minutes from session_start
    ib_end = session_start + timedelta(minutes=60)
    ib_prices = [p["price"] for p in intraday_prices if p["timestamp"] <= ib_end]
    all_prices = [p["price"] for p in intraday_prices]

    if len(ib_prices) == 0:
        return None

    ib_high = max(ib_prices)
    ib_low = min(ib_prices)
    ib_range = ib_high - ib_low

    if ib_range <= 0:
        return None

    day_high = max(all_prices)
    day_low = min(all_prices)

    re_up = max(0.0, day_high - ib_high)
    re_down = max(0.0, ib_low - day_low)

    rea = (re_up - re_down) / ib_range

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

    # Defaults for thresholds
    settings = settings or {}
    gap_acceptance_threshold = settings.get("dir_gap_acceptance_threshold", 0.65)
    acceptance_neutral_threshold = settings.get("dir_acceptance_neutral_threshold", 0.5)
    rea_bull_threshold = settings.get("dir_rea_bull_threshold", 0.3)
    rea_bear_threshold = settings.get("dir_rea_bear_threshold", -0.3)
    rea_neutral_abs_threshold = settings.get("dir_rea_neutral_abs_threshold", 0.3)
    de_directional_threshold = settings.get("dir_de_directional_threshold", 0.5)
    de_neutral_threshold = settings.get("dir_de_neutral_threshold", 0.3)

    # Ensure history is sorted by time
    history_sorted = sorted(price_history, key=lambda p: p["timestamp"])
    intraday_prices = history_sorted

    # Current open / close for today
    open_price = intraday_prices[0]["price"]
    close_price = intraday_prices[-1]["price"]

    # For now, previous day close/range unknown → pass None values
    opening = calculate_gap_and_acceptance(
        open_price=open_price,
        previous_close=None,
        previous_day_range=None,
        intraday_prices=intraday_prices,
        session_start=market_open_time,
        gap_acceptance_threshold=gap_acceptance_threshold,
        acceptance_neutral_threshold=acceptance_neutral_threshold,
    )

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


