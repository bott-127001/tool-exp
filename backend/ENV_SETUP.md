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

## Step 6: Add Upstox Login Credentials (for Automated OAuth)

For automated daily OAuth login, add these credentials:

```env
# Phone number used to login to Upstox
UPSTOX_SAMARTH_PHONE=your_samarth_phone_number
# TOTP secret (base32 encoded) from your authenticator app
UPSTOX_SAMARTH_TOTP_SECRET=your_samarth_totp_base32_secret
# 6-digit Upstox PIN
UPSTOX_SAMARTH_PIN=123456

UPSTOX_PRAJWAL_PHONE=your_prajwal_phone_number
UPSTOX_PRAJWAL_TOTP_SECRET=your_prajwal_totp_base32_secret
UPSTOX_PRAJWAL_PIN=123456
```

**Getting TOTP Secret:**
- Extract the base32 secret from your authenticator app (Google Authenticator, Authy, etc.)
- You may need to use a QR code scanner or app settings to get the raw secret
- The secret should be a base32-encoded string

## Step 7: Add Frontend Dashboard Passwords

For frontend dashboard access (separate from Upstox):

```env
FRONTEND_SAMARTH_PASSWORD=your_secure_password
FRONTEND_PRAJWAL_PASSWORD=your_secure_password
```

These passwords will be hashed automatically on first run. Choose strong passwords for security.

## Security Note

⚠️ **NEVER commit your `.env` file to Git!** It contains sensitive credentials. The `.gitignore` file already excludes `.env` files, but always double-check before committing.

