"""
Quick script to verify your redirect URI matches Upstox requirements
Run this before testing OAuth flow
"""
import os
from dotenv import load_dotenv
from urllib.parse import urlencode, quote

load_dotenv()

print("="*70)
print("REDIRECT URI VERIFICATION")
print("="*70)

redirect_uri = os.getenv("UPSTOX_REDIRECT_URI", "http://localhost:8000/auth/callback")
client_id = os.getenv("UPSTOX_SAMARTH_CLIENT_ID", "")

print(f"\n1. Your Redirect URI from .env:")
print(f"   '{redirect_uri}'")
print(f"   Length: {len(redirect_uri)} characters")

print(f"\n2. URL Encoded version (what Upstox will see):")
encoded = quote(redirect_uri, safe='')
print(f"   '{encoded}'")

print(f"\n3. Expected Exact Match in Upstox App Settings:")
print(f"   '{redirect_uri}'")
print(f"   ⚠️  MUST match character-for-character!")

print(f"\n4. Common Issues to Check:")
issues = []
if redirect_uri.startswith("https://"):
    issues.append("❌ Using https:// - should be http:// for localhost")
if redirect_uri.endswith("/"):
    issues.append("❌ Has trailing slash - remove it")
if "127.0.0.1" in redirect_uri:
    issues.append("❌ Using 127.0.0.1 - should use localhost")
if " " in redirect_uri:
    issues.append("❌ Contains spaces - remove them")

if issues:
    for issue in issues:
        print(f"   {issue}")
else:
    print(f"   ✅ No obvious format issues detected")

print(f"\n5. Test OAuth URL (with your client ID):")
if client_id and client_id != "your_samarth_client_id":
    params = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "state": "test"
    }
    test_url = f"https://api.upstox.com/v2/login/authorization/dialog?{urlencode(params)}"
    print(f"   {test_url[:100]}...")
    print(f"   (Full URL: {len(test_url)} chars)")
else:
    print(f"   ⚠️  Client ID not set - cannot generate test URL")

print(f"\n6. ACTION REQUIRED:")
print(f"   Go to: https://account.upstox.com/developer/apps")
print(f"   Find your app")
print(f"   Set Redirect URI to EXACTLY:")
print(f"   '{redirect_uri}'")
print(f"   Save and try again")
print("="*70)

