# NIFTY50 Options Greek-Signature Signal System

## Overview
A real-time options signal identification system for NIFTY50 using Upstox's option chain API with Greeks. Features OAuth2.0 authentication, real-time polling, Greek signature pattern matching, and WebSocket updates to a React dashboard.

## Tech Stack
- **Backend**: Python FastAPI (port 8000)
- **Frontend**: React + Vite (port 5000)
- **Database**: MongoDB (external - requires MONGO_URI configuration)
- **Real-time**: WebSockets

## Project Structure
```
.
├── backend/
│   ├── main.py           # FastAPI app, WebSocket, API endpoints
│   ├── auth.py           # OAuth2 authentication
│   ├── data_fetcher.py   # Upstox API integration, polling
│   ├── database.py       # MongoDB database operations
│   └── requirements.txt  # Python dependencies
├── frontend/
│   ├── src/
│   │   ├── pages/        # React pages (Login, Dashboard, Settings, etc.)
│   │   ├── App.jsx
│   │   └── main.jsx
│   ├── package.json
│   └── vite.config.js
└── run_dev.sh            # Development startup script
```

## Development Setup
1. The development workflow runs both frontend and backend
2. Frontend runs on port 5000 (Vite dev server)
3. Backend runs on port 8000 (FastAPI)
4. Vite proxies API requests to the backend

## Required Environment Variables
The following secrets/environment variables must be configured:
- `MONGO_URI`: MongoDB connection string (required for database)
- Upstox OAuth credentials for user authentication (see backend/.env.example if available)
- `FRONTEND_SAMARTH_PASSWORD` and `FRONTEND_PRAJWAL_PASSWORD` for frontend user accounts

## Deployment
For production, the build process:
1. Builds the React frontend
2. Copies static files to backend/static
3. Runs with gunicorn + uvicorn worker

## Recent Changes
- 2026-01-29: Configured for Replit environment
  - Updated Vite config for port 5000 and allowed hosts
  - Created run_dev.sh for development workflow
  - Configured autoscale deployment
