from fastapi import APIRouter, Query, HTTPException, Request
from fastapi.responses import RedirectResponse, HTMLResponse
import httpx
import os
from typing import Optional
from urllib.parse import urlencode
from dotenv import load_dotenv
from database import store_tokens, get_user_tokens

# Load environment variables from .env file
load_dotenv()

auth_router = APIRouter()

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
async def callback(
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
            refresh_token = token_data.get("refresh_token")
            expires_in = token_data.get("expires_in", 3600)
            
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
            
            # Calculate expiration timestamp
            import time
            expires_at = int(time.time()) + expires_in
            
            # Store tokens in database
            store_tokens(state, access_token, refresh_token, expires_at)
            
            # Enable polling after successful login
            from data_fetcher import enable_polling
            enable_polling()
            
            # Redirect to frontend dashboard with status code 302
            print(f"✓ Authentication successful for user: {state}")
            print(f"✓ Polling enabled - data fetching will start")
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
    tokens = get_user_tokens(user)
    if tokens:
        # Check if token is expired
        import time
        if tokens["token_expires_at"] > time.time():
            return {"authenticated": True}
    
    return {"authenticated": False}


@auth_router.post("/logout/{user}")
async def logout(user: str):
    """Logout a user by clearing their tokens and stopping polling"""
    from database import get_db_connection
    import sqlite3
    from data_fetcher import disable_polling
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE users 
        SET access_token = NULL, refresh_token = NULL, token_expires_at = NULL
        WHERE username = ?
    """, (user,))
    conn.commit()
    conn.close()
    
    # Disable polling on logout
    disable_polling()
    
    print(f"✓ Logged out {user} - tokens cleared and polling stopped")
    return {"message": f"Logged out {user} successfully"}
