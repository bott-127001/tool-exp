from typing import List, Dict, Tuple


def find_atm_strike(underlying_price: float, options: List[Dict]) -> float:
    """Find the ATM (At-The-Money) strike closest to underlying price"""
    if not options:
        return round(underlying_price / 50) * 50  # Nifty strikes are in multiples of 50
    
    # Get unique strikes
    strikes = sorted(set(opt["strike"] for opt in options))
    
    # Find closest strike to underlying price
    atm_strike = min(strikes, key=lambda x: abs(x - underlying_price))
    
    return atm_strike


def get_atm_plus_otm_options(options: List[Dict], atm_strike: float, 
                             option_type: str, count: int = 10) -> List[Dict]:
    """
    Get ATM strike + N OTM strikes for Calls or Puts
    
    For Calls: ATM, ATM+50, ATM+100, ..., ATM+(count*50)
    For Puts: ATM, ATM-50, ATM-100, ..., ATM-(count*50)
    """
    # Filter by type
    filtered = [opt for opt in options if opt["type"] == option_type]
    
    if not filtered:
        return []
    
    # Get unique strikes sorted
    strikes = sorted(set(opt["strike"] for opt in filtered))
    
    # Find ATM index
    try:
        atm_index = strikes.index(atm_strike)
    except ValueError:
        # ATM strike not found, use closest
        atm_index = min(range(len(strikes)), key=lambda i: abs(strikes[i] - atm_strike))
    
    # Select strikes based on option type
    selected_strikes = []
    
    if option_type == "CE":
        # For Calls: ATM and strikes above (OTM)
        end_index = min(atm_index + count + 1, len(strikes))
        selected_strikes = strikes[atm_index:end_index]
    else:  # PE
        # For Puts: ATM and strikes below (OTM)
        start_index = max(0, atm_index - count)
        selected_strikes = strikes[start_index:atm_index + 1]
        selected_strikes.reverse()  # Keep ATM first
    
    # Return options for selected strikes
    result = []
    for strike in selected_strikes:
        for opt in filtered:
            if opt["strike"] == strike:
                result.append(opt)
                break
    
    return result


def aggregate_call_put_greeks(normalized_data: Dict) -> Dict:
    """
    Aggregate Greeks for Call and Put sides
    Uses ATM + 10 OTM strikes for each side
    """
    options = normalized_data.get("options", [])
    if not options:
        # Return empty aggregated Greeks if no options
        return {
            "call": {"delta": 0, "vega": 0, "theta": 0, "gamma": 0, "option_count": 0},
            "put": {"delta": 0, "vega": 0, "theta": 0, "gamma": 0, "option_count": 0}
        }
    
    atm_strike = normalized_data.get("atm_strike", 0)
    
    # Get Call options (ATM + 10 OTM)
    call_options = get_atm_plus_otm_options(options, atm_strike, "CE", count=10)
    
    # Get Put options (ATM + 10 OTM)
    put_options = get_atm_plus_otm_options(options, atm_strike, "PE", count=10)
    
    # Aggregate Call Greeks (simple sum)
    call_delta = sum(opt.get("delta", 0) for opt in call_options)
    call_vega = sum(opt.get("vega", 0) for opt in call_options)
    call_theta = sum(opt.get("theta", 0) for opt in call_options)
    call_gamma = sum(opt.get("gamma", 0) for opt in call_options)
    
    # Aggregate Put Greeks (simple sum)
    put_delta = sum(opt.get("delta", 0) for opt in put_options)
    put_vega = sum(opt.get("vega", 0) for opt in put_options)
    put_theta = sum(opt.get("theta", 0) for opt in put_options)
    put_gamma = sum(opt.get("gamma", 0) for opt in put_options)
    
    return {
        "call": {
            "delta": call_delta,
            "vega": call_vega,
            "theta": call_theta,
            "gamma": call_gamma,
            "option_count": len(call_options)
        },
        "put": {
            "delta": put_delta,
            "vega": put_vega,
            "theta": put_theta,
            "gamma": put_gamma,
            "option_count": len(put_options)
        }
    }

