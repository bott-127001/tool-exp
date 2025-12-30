# OAuth Redirect Troubleshooting Guide

If you're being redirected to `https://account.upstox.com/` instead of your dashboard, follow these steps:

## Step 1: Verify Redirect URI in Upstox App Settings

**This is the most common cause of the issue!**

1. Go to https://account.upstox.com/developer/apps
2. Select your app (or create one if you haven't)
3. Check the **Redirect URI** field
4. It must be **exactly**: `http://localhost:8000/auth/callback`
   - ✅ Correct: `http://localhost:8000/auth/callback`
   - ❌ Wrong: `https://localhost:8000/auth/callback` (https instead of http)
   - ❌ Wrong: `http://localhost:8000/auth/callback/` (trailing slash)
   - ❌ Wrong: `http://127.0.0.1:8000/auth/callback` (using IP instead of localhost)

5. **Save** the changes in Upstox

## Step 2: Verify Your .env File

Make sure your `.env` file in the `backend` directory has:

```env
UPSTOX_REDIRECT_URI=http://localhost:8000/auth/callback
```

This must match exactly what's in Upstox app settings.

## Step 3: Check Your Backend is Running

1. Make sure your backend is running on port 8000:
   ```bash
   cd backend
   python main.py
   ```

2. Test the callback endpoint directly:
   ```bash
   curl http://localhost:8000/auth/callback
   ```
   (Should return an error about missing parameters, which is expected)

## Step 4: Check Browser Console and Network Tab

1. Open browser DevTools (F12)
2. Go to Network tab
3. Try logging in again
4. Look for:
   - The redirect to Upstox
   - The callback request to `/auth/callback`
   - Any error messages

## Step 5: Common Issues and Solutions

### Issue: "Redirect URI mismatch"
**Solution**: The redirect URI in Upstox app settings doesn't match your `.env` file. They must be identical.

### Issue: "Invalid client_id"
**Solution**: 
- Verify your Client ID in `.env` matches Upstox
- Make sure there are no extra spaces or quotes
- Check if you're using the correct app (Samarth vs Prajwal)

### Issue: Being redirected to Upstox account page after login
**Solution**: 
- Upstox may have logged you out or the session expired
- Try logging out of Upstox account page and try again
- Clear browser cookies for `account.upstox.com`

### Issue: Callback never fires
**Solution**:
- Verify backend is running on port 8000
- Check firewall/antivirus isn't blocking localhost:8000
- Try accessing `http://localhost:8000/` directly to verify server is up

## Step 6: Test the Full Flow

1. **Start backend**: `python main.py`
2. **Open browser**: Go to `http://localhost:3000/login`
3. **Click login button**: Should redirect to Upstox
4. **Login to Upstox**: Complete authentication
5. **After Upstox redirects back**: Should go to `http://localhost:3000/dashboard`

## Debug Mode

If issues persist, check the backend console output when you try to login. The updated code now prints detailed error messages.

## Still Not Working?

Check:
- [ ] Backend is running (port 8000)
- [ ] Redirect URI in Upstox matches `.env` exactly
- [ ] Client ID and Secret are correct in `.env`
- [ ] No typos in `.env` file
- [ ] Browser isn't blocking redirects
- [ ] Upstox app is active/enabled

