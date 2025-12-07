# Fix: Upstox Redirecting to Account Page Instead of Dashboard

## The Problem
After logging in with Upstox, you're being redirected to `https://account.upstox.com/` instead of your dashboard. This means Upstox is **NOT calling your callback URL**.

## Root Cause
**The redirect URI in your Upstox app settings does NOT match exactly** what your application is sending.

## Step-by-Step Fix

### Step 1: Check What Your App is Sending

1. **Start your backend:**
   ```powershell
   cd backend
   python main.py
   ```

2. **Look at the console output** when you click login. You should see:
   ```
   ============================================================
   OAuth Login Request for user: samarth
   Client ID: e4520148-650a-4bf0-bb23-b41bef4150ef
   Redirect URI: http://localhost:8000/auth/callback
   ============================================================
   ```

3. **Copy the exact Redirect URI** shown in the console.

### Step 2: Verify in Upstox Developer Console

1. **Go to:** https://account.upstox.com/developer/apps
2. **Click on your app** (the one with Client ID: `e4520148-650a-4bf0-bb23-b41bef4150ef`)
3. **Find the "Redirect URI" field**
4. **It MUST be EXACTLY:** `http://localhost:8000/auth/callback`

   ⚠️ **Common Mistakes:**
   - ❌ `https://localhost:8000/auth/callback` (using https)
   - ❌ `http://localhost:8000/auth/callback/` (trailing slash)
   - ❌ `http://127.0.0.1:8000/auth/callback` (using IP instead of localhost)
   - ❌ `http://localhost:8000/auth/callback?something=value` (extra parameters)
   - ❌ `localhost:8000/auth/callback` (missing http://)
   - ❌ Any spaces before or after

5. **If it doesn't match exactly:**
   - Click "Edit" or "Update"
   - Enter: `http://localhost:8000/auth/callback`
   - **Save the changes**

### Step 3: Test the Callback URL Directly

1. **While your backend is running**, open your browser
2. **Go to:** `http://localhost:8000/auth/callback-debug`
3. **You should see:** A debug page (this confirms the endpoint is reachable)

### Step 4: Test the Full Flow

1. **Make sure backend is running:**
   ```powershell
   python main.py
   ```

2. **In another terminal, start frontend:**
   ```powershell
   cd frontend
   npm run dev
   ```

3. **Open browser:** http://localhost:3000/login

4. **Click "Login as Samarth"**

5. **Watch the backend console** - you should see:
   - Login request details
   - After Upstox login, callback received

6. **After logging in to Upstox**, you should be redirected to your dashboard, NOT the Upstox account page.

## If It Still Doesn't Work

### Option A: Temporarily Change Redirect URI to Debug Endpoint

1. **Update `.env` file:**
   ```env
   UPSTOX_REDIRECT_URI=http://localhost:8000/auth/callback-debug
   ```

2. **Update Upstox app settings** to match:
   ```
   http://localhost:8000/auth/callback-debug
   ```

3. **Try logging in again** - the debug page will show you exactly what Upstox is sending

### Option B: Check Browser Network Tab

1. **Open Browser DevTools** (F12)
2. **Go to Network tab**
3. **Try logging in**
4. **Look for a request to `/auth/callback`**
   - If you see it: The callback IS being called (check backend logs)
   - If you DON'T see it: Upstox is not redirecting (redirect URI mismatch)

### Option C: Verify Redirect URI is in Upstox's Allowed List

Some OAuth providers have multiple redirect URI fields. Make sure you're setting it in the correct place in Upstox app settings.

## Expected Behavior After Fix

✅ **Correct Flow:**
1. Click "Login as Samarth" 
2. Redirect to Upstox login page
3. Login to Upstox
4. **Upstox redirects to:** `http://localhost:8000/auth/callback?code=XXX&state=samarth`
5. Backend processes the callback
6. **Redirects to:** `http://localhost:3000/dashboard`

❌ **Current (Wrong) Flow:**
1. Click "Login as Samarth"
2. Redirect to Upstox login page  
3. Login to Upstox
4. **Upstox redirects to:** `https://account.upstox.com/` ← **This is wrong!**

## Still Stuck?

If you've verified everything above and it still doesn't work:

1. **Share the backend console output** when you try to login
2. **Share a screenshot** of your Upstox app settings (redact client secret)
3. **Check if Upstox has any additional requirements** in their documentation

