from typing import Dict, List, Tuple, Optional
from database import get_user_settings, log_signal
from calc import aggregate_call_put_greeks

# Greek signature patterns for each position
GREEK_SIGNATURES = {
    "Long Call": {"delta": "+", "vega": "+", "theta": "-", "gamma": "+"},
    "Long Put": {"delta": "-", "vega": "+", "theta": "-", "gamma": "+"},
    "Short Call": {"delta": "-", "vega": "-", "theta": "+", "gamma": "-"},
    "Short Put": {"delta": "+", "vega": "-", "theta": "+", "gamma": "-"}
}

# Global state for consecutive confirmations
signal_confirmation_state: Dict[str, Dict[str, int]] = {}  # {user: {position: count}}


def check_greek_sign(actual_value: float, expected_sign: str, threshold: float) -> Tuple[bool, bool]:
    """
    Check if a Greek value matches the expected sign and threshold
    
    Returns: (sign_match, threshold_match)
    """
    # Check sign
    sign_match = False
    if expected_sign == "+" and actual_value > 0:
        sign_match = True
    elif expected_sign == "-" and actual_value < 0:
        sign_match = True
    
    # Check threshold (absolute value)
    threshold_match = abs(actual_value) >= threshold
    
    return sign_match, threshold_match


def check_position_pattern(aggregated_greeks: Dict, position: str, settings: Dict) -> Dict:
    """
    Check if aggregated Greeks match a position pattern
    
    Returns dict with check results for each Greek
    """
    signature = GREEK_SIGNATURES[position]
    
    # Get aggregated values (using call side for Long/Short Call, put side for Long/Short Put)
    if "Call" in position:
        delta = aggregated_greeks["call"]["delta"]
        vega = aggregated_greeks["call"]["vega"]
        theta = aggregated_greeks["call"]["theta"]
        gamma = aggregated_greeks["call"]["gamma"]
    else:  # Put positions
        delta = aggregated_greeks["put"]["delta"]
        vega = aggregated_greeks["put"]["vega"]
        theta = aggregated_greeks["put"]["theta"]
        gamma = aggregated_greeks["put"]["gamma"]
    
    # Check each Greek
    delta_sign, delta_thresh = check_greek_sign(delta, signature["delta"], settings["delta_threshold"])
    vega_sign, vega_thresh = check_greek_sign(vega, signature["vega"], settings["vega_threshold"])
    theta_sign, theta_thresh = check_greek_sign(theta, signature["theta"], settings["theta_threshold"])
    gamma_sign, gamma_thresh = check_greek_sign(gamma, signature["gamma"], settings["gamma_threshold"])
    
    delta_match = delta_sign and delta_thresh
    vega_match = vega_sign and vega_thresh
    theta_match = theta_sign and theta_thresh
    gamma_match = gamma_sign and gamma_thresh
    
    return {
        "position": position,
        "delta": {"value": delta, "match": delta_match, "sign_match": delta_sign, "threshold_match": delta_thresh},
        "vega": {"value": vega, "match": vega_match, "sign_match": vega_sign, "threshold_match": vega_thresh},
        "theta": {"value": theta, "match": theta_match, "sign_match": theta_sign, "threshold_match": theta_thresh},
        "gamma": {"value": gamma, "match": gamma_match, "sign_match": gamma_sign, "threshold_match": gamma_thresh},
        "all_matched": delta_match and vega_match and theta_match and gamma_match
    }


async def detect_signals(normalized_data: Dict, username: str) -> List[Dict]:
    """
    Detect signals based on Greek signatures
    
    Returns list of signal detection results for all positions
    """
    # Get user settings
    settings = await get_user_settings(username)
    if not settings:
        # Use defaults
        settings = {
            "delta_threshold": 0.20,
            "vega_threshold": 0.10,
            "theta_threshold": 0.02,
            "gamma_threshold": 0.01,
            "consecutive_confirmations": 2
        }
    
    # Aggregate Greeks
    aggregated_greeks = aggregate_call_put_greeks(normalized_data)
    
    # Check all positions
    signals = []
    for position in GREEK_SIGNATURES.keys():
        pattern_result = check_position_pattern(aggregated_greeks, position, settings)
        signals.append(pattern_result)
        
        # Handle consecutive confirmation
        if pattern_result["all_matched"]:
            # Initialize state if needed
            if username not in signal_confirmation_state:
                signal_confirmation_state[username] = {}
            if position not in signal_confirmation_state[username]:
                signal_confirmation_state[username][position] = 0
            
            # Increment confirmation count
            signal_confirmation_state[username][position] += 1
            
            # Check if we've reached required confirmations
            if signal_confirmation_state[username][position] >= settings["consecutive_confirmations"]:
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
                    username=username,
                    position=position,
                    strike_price=strike_price,
                    strike_ltp=strike_ltp,
                    delta=pattern_result["delta"]["value"],
                    vega=pattern_result["vega"]["value"],
                    theta=pattern_result["theta"]["value"],
                    gamma=pattern_result["gamma"]["value"],
                    raw_chain=normalized_data
                )
                
                # Reset counter after logging
                signal_confirmation_state[username][position] = 0
        else:
            # Reset confirmation if pattern doesn't match
            if username in signal_confirmation_state and position in signal_confirmation_state[username]:
                signal_confirmation_state[username][position] = 0
    
    return signals


def get_aggregated_greeks(normalized_data: Dict) -> Dict:
    """Get aggregated Greeks (wrapper function)"""
    return aggregate_call_put_greeks(normalized_data)
