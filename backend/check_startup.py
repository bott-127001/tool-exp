"""
Quick script to check what happens on backend startup
Run this before starting main.py to verify no auto-redirects
"""
import os
from dotenv import load_dotenv

load_dotenv()

print("="*70)
print("BACKEND STARTUP CHECK")
print("="*70)
print("\nChecking for auto-redirect triggers...")

# Check if any code tries to open browser
import sys
modules = sys.modules.keys()
browser_modules = [m for m in modules if 'browser' in m.lower() or 'webbrowser' in m.lower()]
if browser_modules:
    print(f"⚠️  Browser-related modules found: {browser_modules}")
else:
    print("✓ No browser opening modules detected")

# Check if auth URLs are in environment
redirect_uri = os.getenv("UPSTOX_REDIRECT_URI")
if redirect_uri:
    print(f"✓ Redirect URI configured: {redirect_uri}")
else:
    print("⚠️  No redirect URI in environment")

# Check client IDs
samarth_id = os.getenv("UPSTOX_SAMARTH_CLIENT_ID")
prajwal_id = os.getenv("UPSTOX_PRAJWAL_CLIENT_ID")
if samarth_id and samarth_id != "your_samarth_client_id":
    print(f"✓ Samarth client ID configured")
else:
    print("⚠️  Samarth client ID not configured")

if prajwal_id and prajwal_id != "your_prajwal_client_id":
    print(f"✓ Prajwal client ID configured")
else:
    print("⚠️  Prajwal client ID not configured")

print("\n" + "="*70)
print("RECOMMENDATION:")
print("="*70)
print("1. Close ALL browser tabs before starting backend")
print("2. Start backend: python main.py")
print("3. Watch console - it should only show startup messages")
print("4. NO browser windows should open automatically")
print("5. Only open browser manually and go to login page")
print("="*70)

