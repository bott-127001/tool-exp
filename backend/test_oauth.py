"""
Test script to diagnose OAuth configuration
Run this to verify your OAuth setup
"""
import os
from dotenv import load_dotenv
from urllib.parse import urlencode

load_dotenv()

print("="*70)
print("OAuth Configuration Diagnostic")
print("="*70)

# Check environment variables
samarth_client_id = os.getenv("UPSTOX_SAMARTH_CLIENT_ID")
samarth_secret = os.getenv("UPSTOX_SAMARTH_CLIENT_SECRET")
redirect_uri = os.getenv("UPSTOX_REDIRECT_URI", "http://localhost:8000/auth/callback")

print(f"\n1. Client ID (Samarth): {samarth_client_id}")
print(f"   ✓ Set" if samarth_client_id and samarth_client_id != "your_samarth_client_id" else "   ✗ NOT SET or using placeholder")

print(f"\n2. Client Secret (Samarth): {'✓ Set' if samarth_secret and samarth_secret != 'your_samarth_client_secret' else '✗ NOT SET or using placeholder'}")

print(f"\n3. Redirect URI: {redirect_uri}")
print(f"   Expected: http://localhost:8000/auth/callback")
if redirect_uri == "http://localhost:8000/auth/callback":
    print("   ✓ Matches expected value")
else:
    print("   ✗ Does NOT match expected value!")

# Generate test OAuth URL
if samarth_client_id and samarth_client_id != "your_samarth_client_id":
    params = {
        "response_type": "code",
        "client_id": samarth_client_id,
        "redirect_uri": redirect_uri,
        "state": "samarth"
    }
    test_url = f"https://account.upstox.com/oauth/authorize?{urlencode(params)}"
    print(f"\n4. Generated OAuth URL (first 100 chars):")
    print(f"   {test_url[:100]}...")
    print(f"\n   Full URL length: {len(test_url)} characters")

print("\n" + "="*70)
print("CHECKLIST:")
print("="*70)
print("\nIn your Upstox app settings (https://account.upstox.com/developer/apps):")
print(f"  [ ] Redirect URI is set to: {redirect_uri}")
print("  [ ] No trailing slash")
print("  [ ] Using http:// (not https://)")
print("  [ ] Using localhost (not 127.0.0.1)")
print("\nIf any of these don't match, update your Upstox app settings!")
print("="*70)

