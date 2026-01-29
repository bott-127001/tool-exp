"""
Pipeline Architecture for Data Fetching and Calculations

This module provides a clean, sequential pipeline that ensures:
1. Data is fetched every 5 seconds
2. All calculations happen one by one without overlap
3. State is managed safely with proper locking
4. Results are broadcast to frontend after all processing completes
"""

import asyncio
from dataclasses import dataclass, field
from typing import Optional, Dict, List, Any
from datetime import datetime, timedelta, timezone
from enum import Enum


class PipelineStage(Enum):
    """Enum representing the current stage of the pipeline"""
    IDLE = "idle"
    FETCHING = "fetching"
    NORMALIZING = "normalizing"
    AGGREGATING = "aggregating"
    CALCULATING_BASELINE = "calculating_baseline"
    CALCULATING_VOLATILITY = "calculating_volatility"
    CALCULATING_DIRECTION = "calculating_direction"
    DETECTING_SIGNALS = "detecting_signals"
    BROADCASTING = "broadcasting"
    LOGGING = "logging"
    COMPLETE = "complete"


@dataclass
class PriceEntry:
    """A single price entry with timestamp"""
    timestamp: datetime
    price: float


@dataclass
class PipelineState:
    """
    Consolidated state for the entire data pipeline.
    All mutable state is contained here, protected by the pipeline lock.
    """
    latest_data: Optional[Dict] = None
    raw_option_chain: Optional[Dict] = None
    baseline_greeks: Optional[Dict] = None
    
    polling_active: bool = False
    should_poll: bool = False
    current_user: Optional[str] = None
    
    price_history: List[PriceEntry] = field(default_factory=list)
    full_day_price_history: List[PriceEntry] = field(default_factory=list)
    open_price: Optional[float] = None
    open_price_from_candle: Optional[float] = None
    market_open_time: Optional[datetime] = None
    
    data_sequence: int = 0
    last_successful_poll: Optional[datetime] = None
    stall_warning_sent: bool = False
    
    current_stage: PipelineStage = PipelineStage.IDLE
    last_error: Optional[str] = None
    
    signal_confirmation_state: Dict[str, Dict[str, int]] = field(default_factory=dict)
    
    prev_day_stats_fetched_for: Dict[str, str] = field(default_factory=dict)
    current_day_open_candle_fetched_for: Dict[str, str] = field(default_factory=dict)

    def reset_for_new_day(self):
        """Reset state for a new trading day"""
        self.price_history = []
        self.full_day_price_history = []
        self.open_price = None
        self.open_price_from_candle = None
        self.market_open_time = None
        self.baseline_greeks = None
        self.data_sequence = 0
        self.last_successful_poll = None
        self.stall_warning_sent = False
        self.signal_confirmation_state = {}
        self.prev_day_stats_fetched_for = {}
        self.current_day_open_candle_fetched_for = {}
        self.latest_data = None
        self.raw_option_chain = None

    def reset_for_logout(self):
        """Reset state when user logs out"""
        self.latest_data = None
        self.current_user = None
        self.should_poll = False
        self.baseline_greeks = None
        self.price_history = []
        self.full_day_price_history = []
        self.open_price = None
        self.market_open_time = None


class DataPipeline:
    """
    Main pipeline orchestrator that ensures sequential processing
    of all data fetching and calculation stages.
    """
    
    def __init__(self):
        self.state = PipelineState()
        self._lock = asyncio.Lock()
        self._polling_task: Optional[asyncio.Task] = None
        
    async def acquire_lock(self, timeout: float = 10.0) -> bool:
        """
        Acquire the pipeline lock with timeout.
        Returns True if lock acquired, False if timeout.
        """
        try:
            await asyncio.wait_for(self._lock.acquire(), timeout=timeout)
            return True
        except asyncio.TimeoutError:
            print(f"⚠️ Failed to acquire pipeline lock within {timeout}s")
            return False
    
    def release_lock(self):
        """Release the pipeline lock"""
        if self._lock.locked():
            self._lock.release()
    
    async def execute_stage(self, stage: PipelineStage, coro):
        """
        Execute a pipeline stage with proper state tracking.
        The lock must already be held when calling this.
        """
        self.state.current_stage = stage
        try:
            result = await coro
            return result
        except Exception as e:
            self.state.last_error = f"{stage.value}: {str(e)}"
            raise
    
    def get_market_open_time(self, current_time: datetime) -> datetime:
        """Get market open time for the current day (09:15 IST), returned as UTC."""
        if current_time.tzinfo is None:
            current_time_utc = current_time.replace(tzinfo=timezone.utc)
        else:
            current_time_utc = current_time.astimezone(timezone.utc)

        ist = timezone(timedelta(hours=5, minutes=30))
        now_ist = current_time_utc.astimezone(ist)
        market_open_ist = now_ist.replace(hour=9, minute=15, second=0, microsecond=0)
        market_open_utc = market_open_ist.astimezone(timezone.utc)
        return market_open_utc

    def update_price_history(self, current_price: float, current_time: datetime):
        """
        Update price history with new price entry.
        Must be called while holding the lock.
        """
        today_market_open = self.get_market_open_time(current_time)
        
        if (self.state.market_open_time is None or 
            today_market_open.date() != self.state.market_open_time.date()):
            self.state.price_history = []
            self.state.full_day_price_history = []
            
            if self.state.open_price_from_candle is not None:
                self.state.open_price = self.state.open_price_from_candle
                print(f"📊 New trading day. Using accurate open price from candle: {self.state.open_price}")
            else:
                self.state.open_price = current_price
                print(f"📊 New trading day. Open price (from spot): {self.state.open_price}")
            self.state.market_open_time = today_market_open
        
        price_entry = PriceEntry(timestamp=current_time, price=current_price)
        self.state.price_history.append(price_entry)
        self.state.full_day_price_history.append(price_entry)
        
        cutoff_time = current_time - timedelta(minutes=15)
        self.state.price_history = [
            p for p in self.state.price_history 
            if p.timestamp >= cutoff_time
        ]

    def get_price_15min_ago(self, current_time: datetime) -> Optional[float]:
        """Get price from approximately 15 minutes ago."""
        cutoff_time = current_time - timedelta(minutes=15)
        
        closest_price = None
        min_diff = float('inf')
        
        for price_entry in self.state.price_history:
            time_diff = abs((price_entry.timestamp - cutoff_time).total_seconds())
            if time_diff < min_diff:
                min_diff = time_diff
                closest_price = price_entry.price
        
        if min_diff <= 120:
            return closest_price
        return None

    def is_market_hours(self) -> bool:
        """Check if current time is within market hours (09:15 - 15:30 IST)"""
        now_utc = datetime.now(timezone.utc)
        now_ist = now_utc + timedelta(hours=5, minutes=30)
        
        if now_ist.weekday() >= 5:
            return False
        
        current_time = now_ist.time()
        start_time = datetime.strptime("09:15", "%H:%M").time()
        end_time = datetime.strptime("15:30", "%H:%M").time()
        
        return start_time <= current_time <= end_time

    def get_full_day_prices_as_dicts(self) -> List[Dict]:
        """Convert full day price history to dict format for calculations."""
        return [
            {"timestamp": p.timestamp, "price": p.price}
            for p in self.state.full_day_price_history
        ]

    def get_rolling_prices_as_dicts(self) -> List[Dict]:
        """Convert rolling price history to dict format for calculations."""
        return [
            {"timestamp": p.timestamp, "price": p.price}
            for p in self.state.price_history
        ]


pipeline = DataPipeline()
