from fastapi import APIRouter, Query, HTTPException, Request
from fastapi.responses import RedirectResponse, HTMLResponse, JSONResponse
import httpx
import os
import secrets
import asyncio
from typing import Optional
from urllib.parse import urlencode
from dotenv import load_dotenv
from database import (
    store_tokens,
    get_user_tokens,
    clear_user_tokens,
    verify_frontend_user,
    create_frontend_user,
    create_frontend_session,
    get_frontend_session,
    delete_frontend_session,
    delete_expired_frontend_sessions,
)
from datetime import datetime, timezone, timedelta
import time

# Load environment variables from .env file
load_dotenv()

auth_router = APIRouter()


def calculate_token_expiration_3am_ist() -> int:
    """
    Calculate token expiration time as 3 AM IST on the next day.
    Upstox tokens expire at 3 AM IST daily regardless of when they're generated.
    """
    now_utc = datetime.now(timezone.utc)
    now_ist = now_utc + timedelta(hours=5, minutes=30)
    
    # If it's before 3 AM IST today, expire at 3 AM today
    # Otherwise, expire at 3 AM tomorrow
    if now_ist.hour < 3:
        # Expire at 3 AM today
        expiration_ist = now_ist.replace(hour=3, minute=0, second=0, microsecond=0)
    else:
        # Expire at 3 AM tomorrow
        expiration_ist = (now_ist + timedelta(days=1)).replace(hour=3, minute=0, second=0, microsecond=0)
    
    # Convert back to UTC
    expiration_utc = (expiration_ist - timedelta(hours=5, minutes=30)).replace(tzinfo=timezone.utc)
    
    # Return as Unix timestamp
    return int(expiration_utc.timestamp())

# Upstox OAuth credentials for each user
# TODO: Replace with actual credentials from environment variables or config
USER_CREDENTIALS = {
    "samarth": {
        "client_id": os.getenv("UPSTOX_SAMARTH_CLIENT_ID", "your_samarth_client_id"),
        "client_secret": os.getenv("UPSTOX_SAMARTH_CLIENT_SECRET", "your_samarth_client_secret"),
        "redirect_uri": os.getenv("UPSTOX_REDIRECT_URI")
    },
    "prajwal": {
        "client_id": os.getenv("UPSTOX_PRAJWAL_CLIENT_ID", "your_prajwal_client_id"),
        "client_secret": os.getenv("UPSTOX_PRAJWAL_CLIENT_SECRET", "your_prajwal_client_secret"),
        "redirect_uri": os.getenv("UPSTOX_REDIRECT_URI")
    }
}

# Upstox OAuth endpoints
# Upstox uses api.upstox.com for the authorization dialog
UPSTOX_AUTH_URL = "https://api.upstox.com/v2/login/authorization/dialog"
UPSTOX_TOKEN_URL = "https://api.upstox.com/v2/login/authorization/token"


@auth_router.get("/test-callback")
async def test_callback(request: Request):
    """Test endpoint to verify callback URL is reachable"""
    return {
        "message": "Callback endpoint is reachable!",
        "query_params": dict(request.query_params),
        "url": str(request.url)
    }


@auth_router.get("/callback-debug")
async def callback_debug(request: Request):
    """Debug version of callback - shows HTML page with OAuth parameters"""
    from fastapi.responses import FileResponse
    import os
    # Return the debug HTML file
    debug_file = os.path.join(os.path.dirname(__file__), "debug_oauth.html")
    if os.path.exists(debug_file):
        return FileResponse(debug_file)
    else:
        # Fallback if file doesn't exist
        params = dict(request.query_params)
        return HTMLResponse(
            content=f"""
            <html><body>
                <h1>Debug Callback</h1>
                <p>URL: {request.url}</p>
                <p>Params: {params}</p>
                <p>Code: {params.get('code', 'None')}</p>
                <p>State: {params.get('state', 'None')}</p>
                <p>Error: {params.get('error', 'None')}</p>
            </body></html>
            """
        )


@auth_router.get("/login")
async def login(user: str = Query(...)):
    """
    Initiate OAuth login for a user
    This endpoint is ONLY called when user clicks login button in frontend
    """
    print(f"\n{'='*70}")
    print(f"🔐 LOGIN REQUEST RECEIVED - User clicked login button for: {user}")
    print(f"{'='*70}")
    
    if user not in USER_CREDENTIALS:
        print(f"❌ Invalid user: {user}")
        raise HTTPException(status_code=400, detail="Invalid user")
    
    credentials = USER_CREDENTIALS[user]
    
    # Validate credentials are set
    if credentials['client_id'] == "your_samarth_client_id" or credentials['client_id'] == "your_prajwal_client_id":
        raise HTTPException(
            status_code=500, 
            detail="Upstox credentials not configured. Please set up your .env file with valid client_id and client_secret."
        )
    
    # URL encode parameters
    redirect_uri = credentials['redirect_uri']
    
    # Verify redirect_uri is set correctly
    if not redirect_uri or redirect_uri == "your_redirect_uri":
        raise HTTPException(
            status_code=500,
            detail="Redirect URI not configured. Please set UPSTOX_REDIRECT_URI in .env file"
        )
    
    # Build OAuth parameters - Upstox requires exact parameter names
    params = {
        "response_type": "code",
        "client_id": credentials['client_id'],
        "redirect_uri": redirect_uri,
        "state": user
    }
    
    auth_url = f"{UPSTOX_AUTH_URL}?{urlencode(params)}"
    
    # # Debug logging - CRITICAL for troubleshooting
    # import traceback
    # print(f"\n{'='*70}")
    # print(f"🔐 OAuth Login Request for user: {user}")
    # print(f"{'='*70}")
    # print(f"⚠️  WARNING: This endpoint was called!")
    # print(f"   This should ONLY happen when user clicks login button")
    # print(f"   If you see this on backend startup, something is wrong!")
    # print(f"\nStack trace (who called this):")
    # for line in traceback.format_stack()[-5:-1]:
    #     print(f"   {line.strip()}")
    # print(f"\nClient ID: {credentials['client_id']}")
    # print(f"Redirect URI: {redirect_uri}")
    # print(f"State: {user}")
    # print(f"\n⚠️  IMPORTANT: The Redirect URI above MUST match EXACTLY in Upstox app settings!")
    # print(f"   Check: https://account.upstox.com/developer/apps")
    # print(f"\nGenerated Auth URL:")
    # print(f"{auth_url}")
    # print(f"{'='*70}\n")
    
    return RedirectResponse(url=auth_url)


@auth_router.get("/callback")
async def callback( # This function is already async, which is great
    request: Request,
    code: Optional[str] = Query(None),
    error: Optional[str] = Query(None),
    error_description: Optional[str] = Query(None),
    state: Optional[str] = Query(None)
):
    """Handle OAuth callback"""
    # # Debug logging
    # print(f"\n{'='*60}")
    # print(f"OAuth Callback Received")
    # print(f"Query params: {dict(request.query_params)}")
    # print(f"Code: {code}")
    # print(f"State: {state}")
    # print(f"Error: {error}")
    # print(f"Error Description: {error_description}")
    # print(f"Full URL: {request.url}")
    # print(f"{'='*60}\n")
    
    # Handle OAuth errors
    if error:
        error_msg = error_description or error
        return HTMLResponse(
            content=f"""
            <html>
                <body>
                    <h2>OAuth Error</h2>
                    <p>Error: {error}</p>
                    <p>Description: {error_msg}</p>
                    <p><a href="/login">Go back to login</a></p>
                </body>
            </html>
            """,
            status_code=400
        )
    
    # Validate required parameters
    if not code or not state:
        return HTMLResponse(
            content="""
            <html>
                <body>
                    <h2>Authentication Error</h2>
                    <p>Missing authorization code or state parameter.</p>
                    <p><a href="/login">Go back to login</a></p>
                </body>
            </html>
            """,
            status_code=400
        )
    
    if state not in USER_CREDENTIALS:
        return HTMLResponse(
            content=f"""
            <html>
                <body>
                    <h2>Invalid State</h2>
                    <p>Invalid user state: {state}</p>
                    <p><a href="/login">Go back to login</a></p>
                </body>
            </html>
            """,
            status_code=400
        )
    
    credentials = USER_CREDENTIALS[state]
    
    try:
        # Exchange code for tokens
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                UPSTOX_TOKEN_URL,
                data={
                    "code": code,
                    "client_id": credentials["client_id"],
                    "client_secret": credentials["client_secret"],
                    "redirect_uri": credentials["redirect_uri"],
                    "grant_type": "authorization_code"
                },
                headers={"Accept": "application/json"}
            )
            
            if response.status_code != 200:
                error_text = response.text
                print(f"Token exchange failed: {response.status_code} - {error_text}")
                return HTMLResponse(
                    content=f"""
                    <html>
                        <body>
                            <h2>Token Exchange Failed</h2>
                            <p>Status: {response.status_code}</p>
                            <p>Error: {error_text}</p>
                            <p>Please check:</p>
                            <ul>
                                <li>Your redirect_uri in .env matches Upstox app settings exactly</li>
                                <li>Your client_id and client_secret are correct</li>
                                <li>The authorization code hasn't expired</li>
                            </ul>
                            <p><a href="/login">Go back to login</a></p>
                        </body>
                    </html>
                    """,
                    status_code=400
                )
            
            token_data = response.json()
            
            access_token = token_data.get("access_token")
            
            if not access_token:
                return HTMLResponse(
                    content="""
                    <html>
                        <body>
                            <h2>Authentication Error</h2>
                            <p>No access token received from Upstox.</p>
                            <p><a href="/login">Go back to login</a></p>
                        </body>
                    </html>
                    """,
                    status_code=400
                )
            
            # Upstox doesn't provide refresh tokens, so we always use empty string
            # Tokens expire at 3 AM IST daily regardless of generation time
            refresh_token = ""
            
            # Calculate expiration timestamp - always 3 AM IST next day
            expires_at = calculate_token_expiration_3am_ist()
            
            # Store tokens in database
            await store_tokens(state, access_token, refresh_token or "", expires_at)
            
            # If samarth logs in, also store tokens for prajwal (samarth's login feeds both)
            if state == "samarth":
                await store_tokens("prajwal", access_token, refresh_token or "", expires_at)
                print(f"✓ Also stored tokens for prajwal (samarth's login feeds both users)")
            
            # Verify tokens were stored correctly
            stored_tokens = await get_user_tokens(state)
            if not stored_tokens or not stored_tokens.get("access_token"):
                print(f"❌ ERROR: Tokens were not stored correctly for {state}")
                raise Exception("Token storage verification failed")
            
            # Enable polling after successful login
            from data_fetcher import enable_polling
            enable_polling()
            
            # Redirect to frontend dashboard with status code 302
            # Calculate time until expiration for logging
            expires_in_seconds = expires_at - int(time.time())
            expires_in_hours = expires_in_seconds / 3600
            
            print(f"✓ Authentication successful for user: {state}")
            print(f"✓ Access token stored: {access_token[:20]}...")
            print(f"✓ Token expires at 3 AM IST (in {expires_in_hours:.1f} hours)")
            print(f"✓ Token storage verified in database")
            print(f"✓ Polling enabled - data fetching will start immediately")
            print(f"✓ Redirecting to dashboard...")
            return RedirectResponse(url="/dashboard", status_code=302)
    
    except Exception as e:
        print(f"Error in callback: {str(e)}")
        return HTMLResponse(
            content=f"""
            <html>
                <body>
                    <h2>Server Error</h2>
                    <p>An error occurred during authentication: {str(e)}</p>
                    <p><a href="/login">Go back to login</a></p>
                </body>
            </html>
            """,
            status_code=500
        )


@auth_router.get("/check/{user}")
async def check_auth(user: str):
    """Check if user is authenticated"""
    tokens = await get_user_tokens(user)
    if tokens:
        # Check if token is expired
        import time
        if tokens.get("token_expires_at") and tokens["token_expires_at"] > time.time():
            return {"authenticated": True}
    
    return {"authenticated": False}


@auth_router.post("/logout")
async def logout():
    """Logout a user by clearing their tokens and stopping polling"""
    from data_fetcher import disable_polling, get_current_authenticated_user
    
    # Find the currently authenticated user
    current_user = await get_current_authenticated_user()
    
    if current_user:
        await clear_user_tokens(current_user)
        # Disable polling on logout
        disable_polling()
        print(f"✓ Logged out {current_user} - tokens cleared and polling stopped")
        return {"message": f"Logged out {current_user} successfully"}
    
    # If no user was found to be logged in, still confirm the action
    return {"message": "No active user session found to log out."}


async def refresh_access_token(username: str) -> Optional[str]:
    """
    Upstox tokens cannot be refreshed - they expire at 3 AM IST daily.
    This function is kept for compatibility but always returns None.
    Users must re-login when tokens expire.
    """
    print(f"⚠️  Token refresh attempted for {username}, but Upstox doesn't support refresh tokens.")
    print(f"⚠️  Tokens expire at 3 AM IST daily. User needs to re-login.")
    return None


# Frontend authentication (separate from Upstox OAuth)
# Sessions are stored in MongoDB so they work across multiple workers/instances.


@auth_router.post("/frontend-login")
async def frontend_login(request: Request):
    """
    Frontend dashboard login - separate from Upstox OAuth.
    Verifies username/password and returns session token.
    """
    try:
        body = await request.json()
        username = body.get("username")
        password = body.get("password")
        
        print(f"🔐 Frontend login attempt - Username: {username}")
        
        if not username or not password:
            print(f"❌ Missing username or password")
            raise HTTPException(status_code=400, detail="Username and password required")
        
        # Verify credentials
        print(f"🔍 Verifying credentials for {username}...")
        user = await verify_frontend_user(username, password)
        if not user:
            print(f"❌ Invalid credentials for {username}")
            raise HTTPException(status_code=401, detail="Invalid username or password")
        
        print(f"✅ Credentials verified for {username}")
        
        # Create session token
        session_token = secrets.token_urlsafe(32)
        import time
        expires_at = time.time() + (24 * 60 * 60)  # 24 hours
        
        await create_frontend_session(session_token=session_token, username=username, expires_at=expires_at)
        
        print(f"✅ Frontend login successful for {username}")
        return JSONResponse(content={
            "success": True,
            "session_token": session_token,
            "username": username
        })
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Frontend login error: {str(e)}")
        raise HTTPException(status_code=500, detail="Login failed")


@auth_router.post("/frontend-logout")
async def frontend_logout(request: Request):
    """Logout frontend user by clearing session"""
    try:
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            session_token = auth_header.split("Bearer ")[1]
            session = await get_frontend_session(session_token)
            if session:
                username = session.get("username")
                await delete_frontend_session(session_token)
                print(f"✅ Frontend logout successful for {username}")
                return JSONResponse(content={"success": True, "message": "Logged out"})
        
        return JSONResponse(content={"success": True, "message": "No active session"})
    except Exception as e:
        print(f"❌ Frontend logout error: {str(e)}")
        return JSONResponse(content={"success": True, "message": "Logout completed"})


@auth_router.get("/frontend-check")
async def frontend_check(request: Request):
    """Check if frontend user is authenticated"""
    try:
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return JSONResponse(content={"authenticated": False})
        
        session_token = auth_header.split("Bearer ")[1]

        import time
        # Opportunistic cleanup (best-effort)
        try:
            await delete_expired_frontend_sessions(time.time())
        except Exception:
            pass

        session = await get_frontend_session(session_token)
        if session:
            if session.get("expires_at", 0) > time.time():
                return JSONResponse(content={
                    "authenticated": True,
                    "username": session.get("username")
                })
            else:
                # Session expired, remove it
                await delete_frontend_session(session_token)
        
        return JSONResponse(content={"authenticated": False})
    except Exception as e:
        print(f"❌ Frontend check error: {str(e)}")
        return JSONResponse(content={"authenticated": False})


def get_frontend_user_from_token(session_token: Optional[str]) -> Optional[str]:
    """Helper function to get username from session token"""
    # NOTE: This helper is used by async endpoints; keep it sync-safe by returning None here.
    # Callers should use `get_frontend_user_from_token_async` instead.
    return None


async def get_frontend_user_from_token_async(session_token: Optional[str]) -> Optional[str]:
    """Async helper to get username from session token (Mongo-backed)."""
    if not session_token:
        return None
    import time
    session = await get_frontend_session(session_token)
    if not session:
        return None
    if session.get("expires_at", 0) > time.time():
        return session.get("username")
    await delete_frontend_session(session_token)
    return None


@auth_router.get("/check-upstox-login-status")
async def check_upstox_login_status(request: Request):
    """
    Check if Upstox login happened today for the current frontend user.
    Returns whether login happened today and if token is valid.
    """
    try:
        # Get current frontend user
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Not authenticated")
        
        session_token = auth_header.split("Bearer ")[1]
        username = await get_frontend_user_from_token_async(session_token)
        
        if not username:
            raise HTTPException(status_code=401, detail="Invalid session")
        
        # Get Upstox tokens for this user
        tokens = await get_user_tokens(username)
        
        if not tokens or not tokens.get("access_token"):
            return JSONResponse(content={
                "logged_in_today": False,
                "has_token": False,
                "token_valid": False,
                "login_failed_today": False,
                "message": "No Upstox login found"
            })
        
        # Check if token was updated today
        from datetime import datetime, timezone, timedelta
        import time
        
        updated_at = tokens.get("updated_at")
        has_token = True
        token_valid = False
        logged_in_today = False
        login_failed_today = False
        
        # Check for login failure today
        last_login_failure = tokens.get("last_login_failure")
        if last_login_failure:
            failure_date = last_login_failure.get("date")
            now_utc = datetime.now(timezone.utc)
            now_ist = now_utc + timedelta(hours=5, minutes=30)
            today_str = now_ist.strftime("%Y-%m-%d")
            if failure_date == today_str:
                login_failed_today = True
        
        if updated_at:
            # Convert to IST for comparison
            try:
                if isinstance(updated_at, datetime):
                    # If it's timezone-aware, convert to UTC first, then to IST
                    if updated_at.tzinfo is not None:
                        updated_utc = updated_at.astimezone(timezone.utc)
                    else:
                        # Assume it's UTC if naive
                        updated_utc = updated_at.replace(tzinfo=timezone.utc)
                    updated_ist = updated_utc + timedelta(hours=5, minutes=30)
                else:
                    # If it's a string or other format, try to parse
                    updated_dt = datetime.fromisoformat(str(updated_at).replace('Z', '+00:00'))
                    if updated_dt.tzinfo is None:
                        updated_dt = updated_dt.replace(tzinfo=timezone.utc)
                    updated_utc = updated_dt.astimezone(timezone.utc)
                    updated_ist = updated_utc + timedelta(hours=5, minutes=30)
                
                now_utc = datetime.now(timezone.utc)
                now_ist = now_utc + timedelta(hours=5, minutes=30)
                
                # Check if updated today (same date in IST)
                logged_in_today = (
                    updated_ist.date() == now_ist.date()
                )
            except Exception as e:
                # If parsing fails, assume not logged in today
                print(f"⚠️ Error parsing updated_at: {e}")
                logged_in_today = False
        
        # Check if token is still valid (not expired)
        expires_at = tokens.get("token_expires_at")
        if expires_at:
            token_valid = expires_at > time.time()
        
        # Determine message
        if login_failed_today:
            message = "Automated login failed at 9:15 AM today. Please login manually."
        elif logged_in_today:
            message = "Logged in today"
        else:
            message = "Not logged in today"
        
        return JSONResponse(content={
            "logged_in_today": logged_in_today,
            "has_token": has_token,
            "token_valid": token_valid,
            "login_failed_today": login_failed_today,
            "updated_at": updated_at.isoformat() if updated_at else None,
            "message": message
        })
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error checking Upstox login status: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Error checking login status")


@auth_router.post("/trigger-upstox-login")
async def trigger_upstox_login(request: Request):
    """
    Manually trigger automated Upstox login for the current frontend user.
    """
    try:
        # Get current frontend user
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Not authenticated")
        
        session_token = auth_header.split("Bearer ")[1]
        username = await get_frontend_user_from_token_async(session_token)
        
        if not username:
            raise HTTPException(status_code=401, detail="Invalid session")
        
        if username not in ["samarth", "prajwal"]:
            raise HTTPException(status_code=400, detail="Invalid user for Upstox login")
        
        print(f"🤖 Manual Upstox login triggered for {username}")
        
        # Import and call automated login
        from auto_auth import get_selenium_executor, _run_selenium_login_sync
        from data_fetcher import enable_polling
        
        # Run Selenium in thread pool to prevent worker timeout in production
        loop = asyncio.get_event_loop()
        success = await loop.run_in_executor(
            get_selenium_executor(),
            _run_selenium_login_sync,
            username
        )
        
        if success:
            # Enable polling after successful login
            enable_polling()
            print(f"✅ Manual Upstox login successful for {username}")
            return JSONResponse(content={
                "success": True,
                "message": f"Upstox login successful for {username}"
            })
        else:
            print(f"❌ Manual Upstox login failed for {username}")
            return JSONResponse(content={
                "success": False,
                "message": f"Upstox login failed for {username}. Check backend logs for details."
            }, status_code=500)
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error triggering Upstox login: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error triggering login: {str(e)}")