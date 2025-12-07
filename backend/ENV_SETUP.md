# Environment File Setup Guide

## Step 1: Create the `.env` file

In the `backend` directory, create a new file named `.env` (note the dot at the beginning).

### On Windows:
1. Open File Explorer and navigate to the `backend` folder
2. Right-click in an empty area → New → Text Document
3. Name it `.env` (including the dot at the beginning)
4. Windows may warn you about changing the file extension - click Yes

### Or use PowerShell:
```powershell
cd backend
New-Item -Path .env -ItemType File
```

### Or use Command Prompt:
```cmd
cd backend
type nul > .env
```

## Step 2: Add Your Credentials

Open the `.env` file in a text editor and add your Upstox credentials:

```env
# Upstox OAuth Credentials for Samarth
UPSTOX_SAMARTH_CLIENT_ID=your_actual_samarth_client_id
UPSTOX_SAMARTH_CLIENT_SECRET=your_actual_samarth_client_secret

# Upstox OAuth Credentials for Prajwal
UPSTOX_PRAJWAL_CLIENT_ID=your_actual_prajwal_client_id
UPSTOX_PRAJWAL_CLIENT_SECRET=your_actual_prajwal_client_secret

# OAuth Redirect URI (must match exactly what you configured in Upstox)
UPSTOX_REDIRECT_URI=http://localhost:8000/auth/callback
```

**Important:** 
- Replace `your_actual_samarth_client_id` with the real client ID from Upstox
- Replace `your_actual_samarth_client_secret` with the real client secret
- Do the same for Prajwal's credentials
- **DO NOT** include quotes around the values

## Step 3: Get Your Upstox API Credentials

1. **Log in to Upstox Developer Portal**: https://account.upstox.com/developer/apps

2. **Create/Select Your App**:
   - If you don't have an app, create a new one
   - If you have separate apps for Samarth and Prajwal, use their respective credentials
   - If you have one app, you can use the same credentials for both users

3. **Configure Redirect URI**:
   - In your Upstox app settings, set the redirect URI to: `http://localhost:8000/auth/callback`
   - This MUST match exactly (including http://localhost, not https)

4. **Copy Credentials**:
   - Copy the **Client ID** and **Client Secret**
   - Paste them into your `.env` file

## Step 4: Verify Your .env File

Your `.env` file should look something like this (with real values):

```env
UPSTOX_SAMARTH_CLIENT_ID=ABC123XYZ789
UPSTOX_SAMARTH_CLIENT_SECRET=secret_abc123xyz789
UPSTOX_PRAJWAL_CLIENT_ID=DEF456UVW012
UPSTOX_PRAJWAL_CLIENT_SECRET=secret_def456uvw012
UPSTOX_REDIRECT_URI=http://localhost:8000/auth/callback
```

## Step 5: Test the Setup

1. Make sure the `.env` file is in the `backend` directory (same folder as `main.py`)
2. Start your backend server:
   ```bash
   cd backend
   python main.py
   ```
3. If everything is configured correctly, the server should start without errors

## Troubleshooting

### "ModuleNotFoundError: No module named 'dotenv'"
- Install python-dotenv: `pip install python-dotenv`

### "Your credentials are not valid"
- Double-check you copied the Client ID and Secret correctly (no extra spaces)
- Verify the redirect URI matches exactly in both `.env` and Upstox app settings

### File not found errors
- Make sure the `.env` file is in the `backend` directory
- Make sure the filename is exactly `.env` (not `env.txt` or `.env.txt`)

## Security Note

⚠️ **NEVER commit your `.env` file to Git!** It contains sensitive credentials. The `.gitignore` file already excludes `.env` files, but always double-check before committing.

