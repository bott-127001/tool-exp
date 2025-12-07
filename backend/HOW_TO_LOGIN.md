# How to Login and Start Polling

## Current Behavior

The system stores authentication tokens in the database. This means:

1. **After first login**: Tokens are saved
2. **On next backend restart**: If tokens are still valid, polling starts automatically
3. **If you want fresh login**: Clear tokens first

## To Start Fresh (Force Login)

1. **Clear stored tokens:**
   ```powershell
   cd backend
   python clear_auth.py
   ```

2. **Start backend:**
   ```powershell
   python main.py
   ```

3. **Start frontend** (in another terminal):
   ```powershell
   cd frontend
   npm run dev
   ```

4. **Go to login page:**
   - Open browser: http://localhost:3000/login
   - Click "Login as Samarth" or "Login as Prajwal"
   - Complete Upstox OAuth
   - You'll be redirected to dashboard
   - Polling will start automatically

## Token Persistence

Tokens are stored in `options_signals.db` and persist between sessions. This is by design so you don't have to login every time.

To force re-login, run `clear_auth.py` before starting the backend.

