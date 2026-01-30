"""
Data Logger for NIFTY50 Options Signal System
Logs all calculated values to CSV every 5 seconds during market hours (9:15 AM - 3:30 PM IST)
"""

import asyncio
import csv
import os
from datetime import datetime, time, timedelta, timezone
from typing import Optional, Dict, Any

IST = timezone(timedelta(hours=5, minutes=30))
MARKET_OPEN = time(9, 15)
MARKET_CLOSE = time(15, 30)
LOG_INTERVAL_SECONDS = 5
LOGS_DIR = "logs"


def get_ist_now() -> datetime:
    """Get current time in IST"""
    return datetime.now(IST)


def is_market_hours() -> bool:
    """Check if current time is within market hours (9:15 AM - 3:30 PM IST)"""
    now = get_ist_now()
    current_time = now.time()
    return MARKET_OPEN <= current_time <= MARKET_CLOSE


def get_csv_filename() -> str:
    """Generate daily CSV filename with date stamp"""
    today = get_ist_now().strftime("%Y-%m-%d")
    return os.path.join(LOGS_DIR, f"nifty_signals_{today}.csv")


def get_csv_headers() -> list:
    """Return CSV column headers"""
    return [
        "timestamp",
        "spot_price",
        "day_open_price",
        "prev_day_close",
        "prev_day_range",
        "prev_day_date",
        "rv_ratio",
        "rv_ratio_delta",
        "rv_current",
        "rv_open_normalized",
        "iv_atm_cluster",
        "iv_vwap",
        "volatility_state",
        "gap",
        "gap_pct",
        "acceptance_ratio",
        "opening_bias",
        "ib_high",
        "ib_low",
        "ib_range",
        "re_up",
        "re_down",
        "rea",
        "de_value",
        "directional_state",
    ]


def extract_data_row(latest_data: Optional[Dict]) -> Optional[Dict[str, Any]]:
    """Extract all required fields from pipeline data"""
    if not latest_data:
        return None
    
    volatility = latest_data.get("volatility_metrics") or {}
    direction = latest_data.get("direction_metrics") or {}
    opening = direction.get("opening") or {}
    rea_data = direction.get("rea") or {}
    
    settings = {}
    try:
        from pipeline_worker import pipeline
        if pipeline.state:
            state = pipeline.state
            if hasattr(state, 'settings') and state.settings:
                settings = state.settings
    except:
        pass
    
    return {
        "timestamp": get_ist_now().strftime("%Y-%m-%d %H:%M:%S"),
        "spot_price": latest_data.get("underlying_price"),
        "day_open_price": latest_data.get("open_price"),
        "prev_day_close": settings.get("prev_day_close"),
        "prev_day_range": settings.get("prev_day_range"),
        "prev_day_date": settings.get("prev_day_date"),
        "rv_ratio": volatility.get("rv_ratio"),
        "rv_ratio_delta": volatility.get("rv_ratio_delta"),
        "rv_current": volatility.get("rv_current"),
        "rv_open_normalized": volatility.get("rv_open_norm"),
        "iv_atm_cluster": volatility.get("iv_atm"),
        "iv_vwap": volatility.get("iv_vwap"),
        "volatility_state": volatility.get("market_state"),
        "gap": opening.get("gap"),
        "gap_pct": opening.get("gap_pct"),
        "acceptance_ratio": opening.get("acceptance_ratio"),
        "opening_bias": opening.get("bias"),
        "ib_high": rea_data.get("ib_high"),
        "ib_low": rea_data.get("ib_low"),
        "ib_range": rea_data.get("ib_range"),
        "re_up": rea_data.get("re_up"),
        "re_down": rea_data.get("re_down"),
        "rea": rea_data.get("rea"),
        "de_value": direction.get("de"),
        "directional_state": direction.get("directional_state"),
    }


def format_value(value: Any) -> str:
    """Format value for CSV output"""
    if value is None:
        return ""
    if isinstance(value, float):
        return f"{value:.6f}"
    return str(value)


def write_row_to_csv(row: Dict[str, Any], filename: str):
    """Write a single row to CSV file, creating headers if needed"""
    file_exists = os.path.exists(filename)
    headers = get_csv_headers()
    
    with open(filename, 'a', newline='') as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(headers)
        
        row_values = [format_value(row.get(h)) for h in headers]
        writer.writerow(row_values)


async def run_logger():
    """Main logging loop - runs every 5 seconds during market hours"""
    from pipeline_worker import get_latest_data
    
    os.makedirs(LOGS_DIR, exist_ok=True)
    
    print("📊 Data Logger Started")
    print(f"   Logging interval: {LOG_INTERVAL_SECONDS} seconds")
    print(f"   Market hours: {MARKET_OPEN} - {MARKET_CLOSE} IST")
    print(f"   Log directory: {LOGS_DIR}/")
    
    last_log_msg = ""
    
    while True:
        try:
            if is_market_hours():
                latest_data = get_latest_data()
                
                if latest_data:
                    row = extract_data_row(latest_data)
                    if row:
                        filename = get_csv_filename()
                        write_row_to_csv(row, filename)
            else:
                now = get_ist_now()
                msg = f"outside_hours_{now.hour}"
                if msg != last_log_msg:
                    if now.time() < MARKET_OPEN:
                        print(f"📊 Logger: Market not open yet ({now.strftime('%H:%M')} IST)")
                    else:
                        print(f"📊 Logger: Market closed ({now.strftime('%H:%M')} IST)")
                    last_log_msg = msg
                await asyncio.sleep(60)
                continue
                
        except Exception as e:
            print(f"❌ Logger error: {e}")
        
        await asyncio.sleep(LOG_INTERVAL_SECONDS)


def start_logger_sync():
    """Entry point for running logger as standalone script"""
    try:
        asyncio.run(run_logger())
    except KeyboardInterrupt:
        print("\n📊 Data Logger stopped by user")


if __name__ == "__main__":
    start_logger_sync()
