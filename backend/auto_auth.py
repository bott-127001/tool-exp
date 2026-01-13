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
from selenium.common.exceptions import TimeoutException, NoSuchElementException, NoSuchWindowException, WebDriverException
import pyotp
from dotenv import load_dotenv
from auth import USER_CREDENTIALS, UPSTOX_TOKEN_URL, UPSTOX_AUTH_URL
from database import store_tokens
import concurrent.futures
import threading

load_dotenv()

# Thread pool executor - created lazily to avoid startup issues
_selenium_executor = None
_selenium_lock = threading.Lock()  # Thread-safe lock to ensure only one Selenium instance

def get_selenium_executor():
    """Get thread pool executor for Selenium operations."""
    global _selenium_executor
    if _selenium_executor is None:
        _selenium_executor = concurrent.futures.ThreadPoolExecutor(
            max_workers=1,  # Only 1 worker to prevent memory issues
            thread_name_prefix="selenium"
        )
    return _selenium_executor

def _check_window_alive(driver) -> bool:
    """Check if the browser window is still alive."""
    try:
        if driver is None:
            return False
        # Try to get window handles - will raise exception if window is closed
        driver.window_handles
        return True
    except (NoSuchWindowException, WebDriverException, AttributeError):
        return False

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


def _run_selenium_login_sync(user: str) -> Optional[str]:
    """
    Synchronous wrapper for automated_oauth_login.
    This runs in a thread pool executor to avoid blocking the async event loop.
    Creates a new event loop in the thread since we can't use asyncio.run() 
    when there's already a running event loop.
    """
    # Create a new event loop for this thread
    new_loop = asyncio.new_event_loop()
    asyncio.set_event_loop(new_loop)
    try:
        return new_loop.run_until_complete(automated_oauth_login(user))
    finally:
        new_loop.close()


async def automated_oauth_login(user: str) -> Optional[str]:
    """
    Automate OAuth login flow for a user.
    Flow: OAuth URL → Phone Number → TOTP → 6-digit PIN → Callback
    Returns access_token if successful, None otherwise.
    """
    # Use thread lock to ensure only one Selenium instance at a time
    # Since this runs in a thread pool, we use threading.Lock instead of asyncio.Semaphore
    if _selenium_lock.acquire(blocking=False):
        try:
            return await _do_oauth_login(user)
        finally:
            _selenium_lock.release()
    else:
        print(f"⚠️  Another Selenium operation in progress, skipping {user}")
        return None

async def _do_oauth_login(user: str) -> Optional[str]:
    """
    Internal OAuth login implementation.
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
    
    # Setup Chrome in headless mode with memory optimizations
    chrome_options = Options()
    chrome_options.add_argument("--headless=new")  # Use new headless mode (more efficient)
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1280,720")  # Smaller window to save memory
    chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
    
    # Memory optimization flags
    chrome_options.add_argument("--disable-extensions")
    chrome_options.add_argument("--disable-plugins")
    chrome_options.add_argument("--disable-images")  # Don't load images (saves memory)
    chrome_options.add_argument("--disable-background-networking")
    chrome_options.add_argument("--disable-background-timer-throttling")
    chrome_options.add_argument("--disable-renderer-backgrounding")
    chrome_options.add_argument("--disable-backgrounding-occluded-windows")
    chrome_options.add_argument("--disable-features=TranslateUI")
    chrome_options.add_argument("--renderer-process-limit=1")  # Limit renderer processes
    chrome_options.add_argument("--disable-software-rasterizer")
    chrome_options.add_argument("--disable-setuid-sandbox")
    
    # Optional: Remove --headless to see browser during testing
    # chrome_options.add_argument("--headless")
    
    driver = None
    try:
        from selenium.webdriver.chrome.service import Service
        from selenium.webdriver.chrome.service import Service as ChromeService
        
        # Create service with timeout settings
        service = ChromeService()
        driver = webdriver.Chrome(service=service, options=chrome_options)
        driver.implicitly_wait(10)
        # Set page load timeout to prevent hanging (60 seconds)
        driver.set_page_load_timeout(60)
        # Set script timeout
        driver.set_script_timeout(60)
        
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
        try:
            driver.get(auth_url)
            # Check if window is still alive after navigation
            if not _check_window_alive(driver):
                print(f"❌ Browser window closed during navigation")
                return None
        except (TimeoutException, NoSuchWindowException, WebDriverException) as e:
            print(f"⚠️  Error navigating to OAuth URL: {str(e)}")
            if not _check_window_alive(driver):
                print(f"❌ Browser window closed")
                return None
            # Continue if it's just a timeout
        
        # Step 2: Wait for and fill phone number
        print(f"🔐 Waiting for phone number input...")
        wait = WebDriverWait(driver, 45)  # Increased timeout
        
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
                    # Check window before each attempt
                    if not _check_window_alive(driver):
                        print(f"❌ Browser window closed while waiting for phone field")
                        return None
                    # Use shorter timeout per selector attempt
                    quick_wait = WebDriverWait(driver, 15)
                    phone_field = quick_wait.until(EC.presence_of_element_located((selector_type, selector_value)))
                    break
                except (TimeoutException, NoSuchWindowException, WebDriverException):
                    if not _check_window_alive(driver):
                        print(f"❌ Browser window closed")
                        return None
                    continue
            
            if not phone_field:
                # Check window one more time
                if not _check_window_alive(driver):
                    print(f"❌ Browser window closed")
                    return None
                # Take screenshot before failing
                try:
                    driver.save_screenshot(f"oauth_error_phone_not_found_{user}_{int(time.time())}.png")
                except:
                    pass
                raise TimeoutException("Could not find phone number field")
            
            # Check window before interacting
            if not _check_window_alive(driver):
                print(f"❌ Browser window closed before entering phone")
                return None
            
            phone_field.clear()
            phone_field.send_keys(user_creds["phone"])
            print(f"✅ Phone number entered")
        except (TimeoutException, NoSuchWindowException, WebDriverException) as e:
            print(f"❌ Error with phone number field: {str(e)}")
            if not _check_window_alive(driver):
                print(f"❌ Browser window closed")
                return None
            try:
                driver.save_screenshot(f"oauth_error_phone_{user}_{int(time.time())}.png")
            except:
                pass
            return None
        
        # Step 3: Click "Get OTP" button
        print(f"🔘 Clicking Get OTP button...")
        try:
            if not _check_window_alive(driver):
                print(f"❌ Browser window closed before Get OTP")
                return None
            quick_wait = WebDriverWait(driver, 20)
            get_otp_button = quick_wait.until(EC.element_to_be_clickable((By.ID, "getOtp")))
            if not _check_window_alive(driver):
                print(f"❌ Browser window closed before clicking Get OTP")
                return None
            get_otp_button.click()
            print(f"✅ Clicked Get OTP button")
            await asyncio.sleep(3)  # Wait for OTP to be sent/displayed
            if not _check_window_alive(driver):
                print(f"❌ Browser window closed after Get OTP")
                return None
        except (TimeoutException, NoSuchWindowException, WebDriverException) as e:
            print(f"❌ Error with Get OTP button: {str(e)}")
            if not _check_window_alive(driver):
                print(f"❌ Browser window closed")
                return None
            try:
                driver.save_screenshot(f"oauth_error_getotp_{user}_{int(time.time())}.png")
            except:
                pass
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
                    if not _check_window_alive(driver):
                        print(f"❌ Browser window closed while waiting for TOTP field")
                        return None
                    quick_wait = WebDriverWait(driver, 15)
                    totp_field = quick_wait.until(EC.presence_of_element_located((selector_type, selector_value)))
                    break
                except (TimeoutException, NoSuchWindowException, WebDriverException):
                    if not _check_window_alive(driver):
                        print(f"❌ Browser window closed")
                        return None
                    continue
            
            if totp_field:
                if not _check_window_alive(driver):
                    print(f"❌ Browser window closed before entering TOTP")
                    return None
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
                    if not _check_window_alive(driver):
                        print(f"❌ Browser window closed while waiting for PIN field")
                        return None
                    quick_wait = WebDriverWait(driver, 15)
                    pin_field = quick_wait.until(EC.presence_of_element_located((selector_type, selector_value)))
                    break
                except (TimeoutException, NoSuchWindowException, WebDriverException):
                    if not _check_window_alive(driver):
                        print(f"❌ Browser window closed")
                        return None
                    continue
            
            if pin_field:
                if not _check_window_alive(driver):
                    print(f"❌ Browser window closed before entering PIN")
                    return None
                pin_value = user_creds["pin"]
                print(f"🔐 Entering PIN: {'*' * len(pin_value)}")
                pin_field.clear()
                pin_field.send_keys(pin_value)
                
                # Submit PIN - Click Continue button
                try:
                    if not _check_window_alive(driver):
                        print(f"❌ Browser window closed before PIN Continue")
                        return None
                    quick_wait = WebDriverWait(driver, 20)
                    pin_continue_button = quick_wait.until(EC.element_to_be_clickable((By.ID, "pinContinueBtn")))
                    if not _check_window_alive(driver):
                        print(f"❌ Browser window closed before clicking PIN Continue")
                        return None
                    pin_continue_button.click()
                    print(f"✅ Clicked PIN Continue button")
                    await asyncio.sleep(3)  # Wait for OAuth callback
                    if not _check_window_alive(driver):
                        print(f"❌ Browser window closed after PIN Continue")
                        return None
                except (TimeoutException, NoSuchWindowException, WebDriverException) as e:
                    print(f"❌ Error with PIN Continue button: {str(e)}")
                    if not _check_window_alive(driver):
                        print(f"❌ Browser window closed")
                        return None
                    try:
                        driver.save_screenshot(f"oauth_error_pin_continue_{user}_{int(time.time())}.png")
                    except:
                        pass
                    return None
            else:
                print("⚠️  PIN field not found")
        except TimeoutException:
            print("⚠️  PIN field not found or timeout")
        
        # Step 6: Wait for OAuth consent/redirect and extract authorization code
        print(f"⏳ Waiting for OAuth callback...")
        await asyncio.sleep(5)  # Wait a bit longer for redirect
        
        # Check if window is still alive
        if not _check_window_alive(driver):
            print(f"❌ Browser window closed while waiting for callback")
            return None
        
        # Get redirect URI base for comparison
        redirect_uri_base = credentials['redirect_uri'].split('?')[0]
        
        # Check current URL for callback
        try:
            current_url = driver.current_url
            print(f"📍 Initial URL after PIN: {current_url}")
        except (NoSuchWindowException, WebDriverException):
            print(f"❌ Browser window closed when getting URL")
            return None
        
        # Wait for redirect to callback URL (with code parameter)
        # Upstox redirects to the callback URL after successful authentication
        max_wait = 45  # Increased wait time
        wait_time = 0
        callback_received = False
        
        while wait_time < max_wait:
            if not _check_window_alive(driver):
                print(f"❌ Browser window closed during callback wait")
                return None
            try:
                current_url = driver.current_url
                print(f"📍 Checking URL (attempt {wait_time + 1}/{max_wait}): {current_url}")
                
                # Check if we have the authorization code
                if "code=" in current_url:
                    print(f"✅ Found authorization code in URL!")
                    callback_received = True
                    break
                
                # Check if we're at the callback URL (even without code yet, might be loading)
                if redirect_uri_base in current_url:
                    print(f"✅ Reached callback URL: {current_url}")
                    # Wait a bit more to see if code appears
                    await asyncio.sleep(2)
                    current_url = driver.current_url
                    if "code=" in current_url:
                        callback_received = True
                        break
                
                # Check if we're stuck on login page (error case)
                if "/login" in current_url and "code=" not in current_url:
                    if wait_time > 10:  # Only log after waiting a bit
                        print(f"⚠️  Still on login page after {wait_time} seconds")
                
            except (NoSuchWindowException, WebDriverException) as e:
                print(f"❌ Browser window closed: {str(e)}")
                return None
            except Exception as e:
                print(f"⚠️  Error checking URL: {str(e)}")
            
            await asyncio.sleep(1)
            wait_time += 1
        
        if not _check_window_alive(driver):
            print(f"❌ Browser window closed before final URL check")
            return None
        
        try:
            current_url = driver.current_url
            print(f"📍 Final URL: {current_url}")
        except (NoSuchWindowException, WebDriverException):
            print(f"❌ Browser window closed when getting final URL")
            return None
        
        if not callback_received:
            print(f"⚠️  Callback not received within {max_wait} seconds")
            print(f"   Final URL: {current_url}")
            print(f"   Expected redirect URI base: {redirect_uri_base}")
            # Note: Token checking removed to avoid event loop errors
            # The callback endpoint will handle token storage if OAuth succeeds
        
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
            # Note: Token checking removed to avoid event loop errors
            # The callback endpoint will handle token storage if OAuth succeeds
            
            # Take screenshot for debugging
            try:
                driver.save_screenshot(f"oauth_error_{user}_{int(time.time())}.png")
            except:
                pass
            return None
            
    except (TimeoutException, NoSuchWindowException, WebDriverException) as e:
        print(f"❌ Error during automated login: {str(e)}")
        if driver and _check_window_alive(driver):
            try:
                driver.save_screenshot(f"oauth_timeout_{user}_{int(time.time())}.png")
            except:
                pass
        return None
    except Exception as e:
        print(f"❌ Error during automated login: {str(e)}")
        import traceback
        traceback.print_exc()
        if driver and _check_window_alive(driver):
            try:
                driver.save_screenshot(f"oauth_exception_{user}_{int(time.time())}.png")
            except:
                pass
        return None
    finally:
        if driver:
            try:
                driver.quit()
            except:
                pass


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
            target_hour = 15
            target_minute = 34
            

            
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
                    # Run Selenium in thread pool to prevent worker timeout in production
                    # Selenium operations are blocking, so we run them in a separate thread
                    loop = asyncio.get_event_loop()
                    success = await loop.run_in_executor(
                        get_selenium_executor(),
                        _run_selenium_login_sync,
                        user
                    )
                    if success:
                        print(f"✅ Successfully refreshed token for {user}")
                    else:
                        print(f"❌ Failed to refresh token for {user}")
                except Exception as e:
                    print(f"❌ Error refreshing token for {user}: {str(e)}")
                    import traceback
                    traceback.print_exc()
            
            print(f"✅ Daily token refresh completed\n")
            
        except Exception as e:
            print(f"❌ Error in token refresh scheduler: {str(e)}")
            import traceback
            traceback.print_exc()
            # Wait 1 hour before retrying on error
            await asyncio.sleep(3600)
