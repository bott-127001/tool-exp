from typing import Dict

def aggregate_greeks_atm_otm(normalized_data: Dict) -> Dict:
    """
    Aggregate Greeks for ATM + 10 OTM strikes.
    This is a utility function to be shared across modules.
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
            for greek in call_greeks:
                if greek != "option_count": call_greeks[greek] += opt.get(greek, 0)
            call_greeks['option_count'] += 1
        elif opt['type'] == 'PE' and opt['strike'] in put_strikes:
            for greek in put_greeks:
                if greek != "option_count": put_greeks[greek] += opt.get(greek, 0)
            put_greeks['option_count'] += 1
            
    return {"call": call_greeks, "put": put_greeks}