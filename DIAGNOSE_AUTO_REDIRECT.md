# Diagnose Auto-Redirect Issue

## The Problem
Browser is opening automatically when backend starts, showing the Upstox auth URL.

## Diagnostic Steps

### Step 1: Completely Isolate the Backend

1. **Close ALL browser windows and tabs**
2. **Close the frontend** (if running)
3. **Start ONLY the backend:**
   ```powershell
   cd backend
   python main.py
   ```

4. **Watch the console output carefully**

   You should see:
   ```
   ======================================================================
   STARTING BACKEND SERVER
   ======================================================================
   Server will start on: http://0.0.0.0:8000
   NOTE: No browser will open automatically!
   You must manually visit: http://localhost:3000/login
   ======================================================================

   Database initialized
   Backend server ready. Polling will start automatically when a user authenticates.
   Polling worker started. Waiting for user authentication...
   ```

   **If you see this line:**
   ```
   🔐 OAuth Login Request for user: ...
   ```
   **THEN something is calling the login endpoint automatically!**

### Step 2: Check What's Calling the Endpoint

If you see the login request message, it will also show a stack trace. This will tell us WHAT is calling the endpoint.

### Step 3: Check for Auto-Refresh

1. Open browser DevTools (F12)
2. Go to Network tab
3. Check "Preserve log"
4. Start backend
5. See if any requests appear automatically

### Step 4: Check Browser Settings

Some browsers have:
- Auto-refresh extensions
- Restore previous session (opens old tabs)
- Homepage set to localhost URLs

### Step 5: Check if Frontend is Running

If frontend is running in another terminal:
1. Stop it completely
2. Restart backend
3. See if browser still opens

## Common Causes

1. **Browser Restore Session**: Browser remembers last tabs and reopens them
2. **Frontend Auto-Refresh**: Frontend might be polling/refreshing
3. **Bookmark/Favorite**: A bookmark to localhost:8000/auth/login might exist
4. **Browser Extension**: Some extensions auto-refresh tabs
5. **Windows/Taskbar Pinned Site**: Pinned site that auto-opens

## Solution

If browser opens automatically:
1. **DO NOT CLICK ANYTHING**
2. **Immediately check backend console**
3. **Look for the stack trace in the logs**
4. **Copy the full console output and share it**

This will help identify what's triggering the automatic redirect.

