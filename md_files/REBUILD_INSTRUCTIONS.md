# Rebuild Instructions

After making changes, you need to rebuild the frontend and restart the backend:

## Steps:

1. **Build the Frontend:**
   ```powershell
   cd frontend
   npm run build
   cd ..
   ```

2. **Copy built files to backend:**
   ```powershell
   # Remove old static files
   Remove-Item -Recurse -Force backend\static\*
   
   # Copy new build
   Copy-Item -Recurse frontend\dist\* backend\static\
   ```

3. **Restart the Backend Server:**
   - Stop the current backend server (Ctrl+C)
   - Start it again:
   ```powershell
   cd backend
   python main.py
   ```

4. **Clear Browser Cache:**
   - Press Ctrl+Shift+R (or Ctrl+F5) for hard refresh
   - Or open DevTools (F12) → Right-click refresh button → "Empty Cache and Hard Reload"

## Quick Rebuild Script (Windows PowerShell):

Save this as `rebuild.ps1` in the project root:

```powershell
Write-Host "--- Building Frontend ---" -ForegroundColor Green
cd frontend
npm run build
cd ..

Write-Host "--- Copying to Backend Static ---" -ForegroundColor Green
Remove-Item -Recurse -Force backend\static\* -ErrorAction SilentlyContinue
Copy-Item -Recurse frontend\dist\* backend\static\

Write-Host "--- Build Complete! Restart your backend server. ---" -ForegroundColor Green
```

Then run: `.\rebuild.ps1`

