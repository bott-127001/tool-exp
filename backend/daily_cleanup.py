"""
Daily cleanup scheduler that runs at 3 AM IST.
Tasks:
1. Clear daily_baselines from database
2. Null out access tokens in users collection
3. Reset in-memory state in data_fetcher

NOTE:
- We no longer touch the market_data_log collection automatically.
- Market data will stay in MongoDB until you manually export/clear it
  (e.g., via the /api/export-data endpoint or Mongo shell).
"""
import asyncio
import os
from datetime import datetime, timezone, timedelta
from database import (
    db,
    users_collection,
    settings_collection
)

async def clear_daily_baselines():
    """Clear all daily_baselines from database."""
    try:
        result = await db.daily_baselines.delete_many({})
        print(f"✅ Cleared {result.deleted_count} daily_baseline entries from database")
        return result.deleted_count
    except Exception as e:
        print(f"❌ Error clearing daily_baselines: {str(e)}")
        return 0


async def null_out_tokens():
    """Null out access tokens, refresh tokens, and token_expires_at for all users."""
    try:
        result = await users_collection.update_many(
            {},
            {
                "$set": {
                    "access_token": None,
                    "refresh_token": None,
                    "token_expires_at": None
                }
            }
        )
        print(f"✅ Nulled out tokens for {result.modified_count} users")
        return result.modified_count
    except Exception as e:
        print(f"❌ Error nulling out tokens: {str(e)}")
        return 0


async def reset_in_memory_state():
    """Reset in-memory state variables using the pipeline module."""
    try:
        from pipeline_worker import pipeline
        
        # Acquire lock to safely reset state
        lock_acquired = await pipeline.acquire_lock(timeout=10.0)
        if lock_acquired:
            try:
                # Use the comprehensive reset_for_new_day method
                pipeline.state.reset_for_new_day()
                print("✅ Reset in-memory state (baseline_greeks, price_history, latest_data, signal_state)")
            finally:
                pipeline.release_lock()
        else:
            print("⚠️  Could not acquire pipeline lock for state reset")
    except Exception as e:
        print(f"⚠️  Error resetting in-memory state: {str(e)}")
        # Don't fail the whole cleanup if this fails


async def daily_cleanup_task():
    """
    Main cleanup task that runs at 3 AM IST daily.
    Exports market data to CSV and performs housekeeping,
    but does NOT delete market_data_log automatically.
    """
    now_utc = datetime.now(timezone.utc)
    now_ist = now_utc + timedelta(hours=5, minutes=30)
    
    # Get yesterday's date for the export filename (data collected yesterday)
    yesterday = (now_ist - timedelta(days=1)).strftime("%Y-%m-%d")
    
    print(f"\n{'='*70}")
    print(f"🧹 Starting daily cleanup at {now_ist.strftime('%Y-%m-%d %H:%M:%S IST')}")
    print(f"{'='*70}")
    
    try:
        # Step 1: Export market data to CSV (for backup/ML)
        print(f"\n📦 Step 1: Exporting market_data_log to CSV...")
        export_path = await export_market_data_to_csv(yesterday)
        print(f"   Export saved to: {export_path}")
        
        # Step 2: Clear daily_baselines from database
        print(f"\n🗑️  Step 2: Clearing daily_baselines from database...")
        await clear_daily_baselines()
        
        # Step 3: Null out tokens in users collection
        print(f"\n🔐 Step 3: Nulling out access tokens...")
        await null_out_tokens()
        
        # Step 4: Reset in-memory state
        print(f"\n🔄 Step 4: Resetting in-memory state...")
        await reset_in_memory_state()
        
        print(f"\n✅ Daily cleanup completed successfully!")
        print(f"{'='*70}\n")
        
    except Exception as e:
        print(f"\n❌ Error during daily cleanup: {str(e)}")
        import traceback
        traceback.print_exc()
        print(f"{'='*70}\n")


async def token_cleanup_scheduler():
    """
    Background task that runs token cleanup at 3 AM IST daily.
    Only clears access tokens (separate from full daily cleanup which is now manual).
    """
    print("🕐 Token cleanup scheduler started (runs at 3:00 AM IST)")
    
    while True:
        try:
            now_utc = datetime.now(timezone.utc)
            now_ist = now_utc + timedelta(hours=5, minutes=30)
            
            # Target time: 3:00 AM IST
            target_hour = 3
            target_minute = 0
            
            # Calculate next cleanup time
            if now_ist.hour < target_hour or (now_ist.hour == target_hour and now_ist.minute < target_minute):
                # Today at 3:00 AM
                next_cleanup = now_ist.replace(hour=target_hour, minute=target_minute, second=0, microsecond=0)
            else:
                # Tomorrow at 3:00 AM
                next_cleanup = (now_ist + timedelta(days=1)).replace(hour=target_hour, minute=target_minute, second=0, microsecond=0)
            
            # Convert to UTC
            next_cleanup_utc = (next_cleanup - timedelta(hours=5, minutes=30)).replace(tzinfo=timezone.utc)
            wait_seconds = (next_cleanup_utc - now_utc).total_seconds()
            
            print(f"⏰ Next token cleanup scheduled for: {next_cleanup.strftime('%Y-%m-%d %H:%M:%S IST')}")
            print(f"   (Waiting {wait_seconds/3600:.1f} hours)")
            
            # Wait until cleanup time
            await asyncio.sleep(wait_seconds)
            
            # Run token cleanup only
            print(f"\n{'='*70}")
            print(f"🔐 Starting token cleanup at {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
            print(f"{'='*70}")
            await null_out_tokens()
            print(f"✅ Token cleanup completed")
            print(f"{'='*70}\n")
            
        except Exception as e:
            print(f"❌ Error in token cleanup scheduler: {str(e)}")
            import traceback
            traceback.print_exc()
            # Wait 1 hour before retrying on error
            await asyncio.sleep(3600)
