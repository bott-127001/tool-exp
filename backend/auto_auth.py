import asyncio
import os
import time
from datetime import datetime, timezone, timedelta
from typing import Optional
from urllib.parse import urlparse, parse_qs
import httpx
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import pyotp
from dotenv import load_dotenv
from auth import USER_CREDENTIALS, UPSTOX_TOKEN_URL, UPSTOX_AUTH_URL
from database import store_tokens

load_dotenv()

# TOTP secrets from environment (base32 encoded)
TOTP_SECRETS = {
    "samarth": os.getenv("UPSTOX_SAMARTH_TOTP_SECRET", ""),
    "prajwal": os.getenv("UPSTOX_PRAJWAL_TOTP_SECRET", "")
}

# Upstox login credentials (phone number, PIN)
UPSTOX_CREDENTIALS = {
    "samarth": {
        "phone": os.getenv("UPSTOX_SAMARTH_PHONE", ""),
        "pin": os.getenv("UPSTOX_SAMARTH_PIN", "")
    },
    "prajwal": {
        "phone": os.getenv("UPSTOX_PRAJWAL_PHONE", ""),
        "pin": os.getenv("UPSTOX_PRAJWAL_PIN", "")
    }
}


def get_totp_code(user: str) -> str:
    """Generate TOTP code for user"""
    secret = TOTP_SECRETS.get(user)
    if not secret:
        raise ValueError(f"No TOTP secret configured for {user}")
    totp = pyotp.TOTP(secret)
    return totp.now()


async def automated_oauth_login(user: str) -> Optional[str]:
    """
    Automate OAuth login flow for a user.
    Flow: OAuth URL → Phone Number → TOTP → 6-digit PIN → Callback
    Returns access_token if successful, None otherwise.
    """
    print(f"🤖 Starting automated OAuth login for {user}...")
    
    credentials = USER_CREDENTIALS.get(user)
    if not credentials:
        print(f"❌ No credentials found for {user}")
        return None
    
    user_creds = UPSTOX_CREDENTIALS.get(user)
    if not user_creds or not user_creds.get("phone") or not user_creds.get("pin"):
        print(f"❌ Upstox login credentials not configured for {user}")
        return None
    
    # Setup Chrome in headless mode
    chrome_options = Options()
    chrome_options.add_argument("--headless")  # Run in background
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
    
    # Optional: Remove --headless to see browser during testing
    # chrome_options.add_argument("--headless")
    
    driver = None
    try:
        driver = webdriver.Chrome(options=chrome_options)
        driver.implicitly_wait(10)
        
        # Step 1: Navigate to OAuth authorization URL
        from urllib.parse import urlencode
        params = {
            "response_type": "code",
            "client_id": credentials['client_id'],
            "redirect_uri": credentials['redirect_uri'],
            "state": user
        }
        auth_url = f"{UPSTOX_AUTH_URL}?{urlencode(params)}"
        print(f"📱 Navigating to OAuth URL...")
        driver.get(auth_url)
        
        # Step 2: Wait for and fill phone number
        print(f"🔐 Waiting for phone number input...")
        wait = WebDriverWait(driver, 30)
        
        # Find phone number field - adjust selector based on actual Upstox page
        # Common selectors: input[name="mobile"], input[type="tel"], input[id*="phone"]
        try:
            # Try multiple possible selectors
            phone_selectors = [
                (By.ID, "mobileNum"),  # Actual Upstox selector
                (By.ID, "mobileNumber"),
                (By.NAME, "mobileNumber"),
            ]
            
            phone_field = None
            for selector_type, selector_value in phone_selectors:
                try:
                    phone_field = wait.until(EC.presence_of_element_located((selector_type, selector_value)))
                    break
                except TimeoutException:
                    continue
            
            if not phone_field:
                raise TimeoutException("Could not find phone number field")
            
            phone_field.clear()
            phone_field.send_keys(user_creds["phone"])
            print(f"✅ Phone number entered")
        except TimeoutException:
            print(f"❌ Could not find phone number field")
            driver.save_screenshot(f"oauth_error_phone_{user}_{int(time.time())}.png")
            return None
        
        # Step 3: Click "Get OTP" button
        print(f"🔘 Clicking Get OTP button...")
        try:
            get_otp_button = wait.until(EC.element_to_be_clickable((By.ID, "getOtp")))
            get_otp_button.click()
            print(f"✅ Clicked Get OTP button")
            await asyncio.sleep(3)  # Wait for OTP to be sent/displayed
        except TimeoutException:
            print(f"❌ Could not find Get OTP button")
            driver.save_screenshot(f"oauth_error_getotp_{user}_{int(time.time())}.png")
            return None
        
        # Step 4: Handle TOTP
        print(f"🔑 Waiting for TOTP input...")
        await asyncio.sleep(2)  # Wait for page to load
        
        try:
            totp_selectors = [
                (By.ID, "otpNum"),  # Actual Upstox selector
                (By.ID, "totp"),
                (By.NAME, "totp"),
                (By.CSS_SELECTOR, "input[type='text'][maxlength='6']"),
            ]
            
            totp_field = None
            for selector_type, selector_value in totp_selectors:
                try:
                    totp_field = wait.until(EC.presence_of_element_located((selector_type, selector_value)))
                    break
                except TimeoutException:
                    continue
            
            if totp_field:
                totp_code = get_totp_code(user)
                print(f"🔑 Generated TOTP: {totp_code}")
                totp_field.clear()
                totp_field.send_keys(totp_code)
                
                # Submit TOTP - might auto-submit or need Enter key
                await asyncio.sleep(1)  # Brief pause
                try:
                    from selenium.webdriver.common.keys import Keys
                    totp_field.send_keys(Keys.RETURN)
                    print(f"✅ TOTP entered, submitting...")
                    await asyncio.sleep(3)  # Wait for PIN field to appear
                except Exception as e:
                    print(f"⚠️  Could not submit TOTP: {e}")
                    await asyncio.sleep(3)  # Wait anyway
            else:
                print("⚠️  TOTP field not found, may not be required")
        except TimeoutException:
            print("⚠️  TOTP field not found, may not be required")
        
        # Step 5: Handle 6-digit PIN
        print(f"🔐 Waiting for PIN input...")
        await asyncio.sleep(2)
        
        try:
            pin_selectors = [
                (By.ID, "pinCode"),  # Actual Upstox selector
                (By.ID, "pin"),
                (By.NAME, "pin"),
                (By.CSS_SELECTOR, "input[type='password'][maxlength='6']"),
            ]
            
            pin_field = None
            for selector_type, selector_value in pin_selectors:
                try:
                    pin_field = wait.until(EC.presence_of_element_located((selector_type, selector_value)))
                    break
                except TimeoutException:
                    continue
            
            if pin_field:
                pin_value = user_creds["pin"]
                print(f"🔐 Entering PIN: {'*' * len(pin_value)}")
                pin_field.clear()
                pin_field.send_keys(pin_value)
                
                # Submit PIN - Click Continue button
                try:
                    pin_continue_button = wait.until(EC.element_to_be_clickable((By.ID, "pinContinueBtn")))
                    pin_continue_button.click()
                    print(f"✅ Clicked PIN Continue button")
                    await asyncio.sleep(3)  # Wait for OAuth callback
                except TimeoutException:
                    print(f"❌ Could not find PIN Continue button")
                    driver.save_screenshot(f"oauth_error_pin_continue_{user}_{int(time.time())}.png")
                    return None
            else:
                print("⚠️  PIN field not found")
        except TimeoutException:
            print("⚠️  PIN field not found or timeout")
        
        # Step 6: Wait for OAuth consent/redirect and extract authorization code
        print(f"⏳ Waiting for OAuth callback...")
        await asyncio.sleep(3)
        
        # Check current URL for callback
        current_url = driver.current_url
        print(f"📍 Current URL: {current_url}")
        
        # Wait for redirect to callback URL (with code parameter)
        max_wait = 30
        wait_time = 0
        while wait_time < max_wait:
            current_url = driver.current_url
            if "code=" in current_url or credentials['redirect_uri'].split('?')[0] in current_url:
                break
            await asyncio.sleep(1)
            wait_time += 1
        
        current_url = driver.current_url
        print(f"📍 Final URL: {current_url}")
        
        if "code=" in current_url:
            parsed_url = urlparse(current_url)
            query_params = parse_qs(parsed_url.query)
            auth_code = query_params.get("code", [None])[0]
            
            if auth_code:
                print(f"✅ Authorization code received: {auth_code[:20]}...")
                
                # Step 7: Exchange code for access token
                async with httpx.AsyncClient(timeout=30.0) as client:
                    response = await client.post(
                        UPSTOX_TOKEN_URL,
                        data={
                            "code": auth_code,
                            "client_id": credentials["client_id"],
                            "client_secret": credentials["client_secret"],
                            "redirect_uri": credentials["redirect_uri"],
                            "grant_type": "authorization_code"
                        },
                        headers={"Accept": "application/json"}
                    )
                    
                    if response.status_code == 200:
                        token_data = response.json()
                        access_token = token_data.get("access_token")
                        refresh_token = token_data.get("refresh_token", "")
                        expires_in = token_data.get("expires_in", 3600)
                        expires_at = int(time.time()) + expires_in
                        
                        # Store tokens
                        await store_tokens(user, access_token, refresh_token, expires_at)
                        print(f"✅ Automated login successful for {user}")
                        return access_token
                    else:
                        print(f"❌ Token exchange failed: {response.status_code} - {response.text}")
                        return None
            else:
                print(f"❌ No authorization code in callback URL")
                return None
        else:
            print(f"❌ OAuth callback not received. Current URL: {current_url}")
            # Take screenshot for debugging
            driver.save_screenshot(f"oauth_error_{user}_{int(time.time())}.png")
            return None
            
    except Exception as e:
        print(f"❌ Error during automated login: {str(e)}")
        import traceback
        traceback.print_exc()
        if driver:
            driver.save_screenshot(f"oauth_exception_{user}_{int(time.time())}.png")
        return None
    finally:
        if driver:
            driver.quit()


async def daily_token_refresh_scheduler():
    """
    Background task that runs daily before 9:15 AM IST to refresh tokens.
    Runs at 9:15 AM IST (03:45 UTC) to ensure tokens are ready for market open.
    """
    print("🕐 Daily token refresh scheduler started")
    
    while True:
        try:
            now_utc = datetime.now(timezone.utc)
            now_ist = now_utc + timedelta(hours=5, minutes=30)
            
            # Target time: 9:15 AM IST (03:45 UTC)
            target_hour = 10
            target_minute = 45
            
            # Calculate next refresh time
            if now_ist.hour < target_hour or (now_ist.hour == target_hour and now_ist.minute < target_minute):
                # Today at 9:15 AM
                next_refresh = now_ist.replace(hour=target_hour, minute=target_minute, second=0, microsecond=0)
            else:
                # Tomorrow at 9:15 AM
                next_refresh = (now_ist + timedelta(days=1)).replace(hour=target_hour, minute=target_minute, second=0, microsecond=0)
            
            # Convert to UTC
            next_refresh_utc = (next_refresh - timedelta(hours=5, minutes=30)).replace(tzinfo=timezone.utc)
            wait_seconds = (next_refresh_utc - now_utc).total_seconds()
            
            print(f"⏰ Next token refresh scheduled for: {next_refresh.strftime('%Y-%m-%d %H:%M:%S IST')}")
            print(f"   (Waiting {wait_seconds/3600:.1f} hours)")
            
            # Wait until refresh time
            await asyncio.sleep(wait_seconds)
            
            # Check if it's a weekend before attempting login
            now_utc_after_wait = datetime.now(timezone.utc)
            now_ist_after_wait = now_utc_after_wait + timedelta(hours=5, minutes=30)
            
            # Skip weekends (Saturday=5, Sunday=6)
            if now_ist_after_wait.weekday() >= 5:
                print(f"📅 Weekend detected ({now_ist_after_wait.strftime('%A')}). Skipping token refresh.")
                continue
            
            # Refresh tokens for all users
            print(f"\n🔄 Starting daily token refresh at {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
            for user in ["samarth", "prajwal"]:
                try:
                    success = await automated_oauth_login(user)
                    if success:
                        print(f"✅ Successfully refreshed token for {user}")
                    else:
                        print(f"❌ Failed to refresh token for {user}")
                except Exception as e:
                    print(f"❌ Error refreshing token for {user}: {str(e)}")
            
            print(f"✅ Daily token refresh completed\n")
            
        except Exception as e:
            print(f"❌ Error in token refresh scheduler: {str(e)}")
            import traceback
            traceback.print_exc()
            # Wait 1 hour before retrying on error
            await asyncio.sleep(3600)
