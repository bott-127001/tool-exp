# NIFTY50 Options Greek-Signature Signal System

A real-time options signal identification system for NIFTY50 using Upstox's option chain API with Greeks.

## Features

- OAuth2.0 authentication with Upstox (supports 2 users: Samarth and Prajwal)
- Real-time polling every 5 seconds
- Greek signature pattern matching (Long Call, Long Put, Short Call, Short Put)
- Threshold-based signal detection with consecutive confirmation
- Live WebSocket updates to React dashboard
- Trade logs with full signal history
- Configurable thresholds per user

## Tech Stack

- **Backend**: Python FastAPI
- **Frontend**: React with Vite
- **Database**: SQLite
- **API**: Upstox REST API
- **Real-time**: WebSockets

## Setup Instructions

### Backend Setup

1. Navigate to backend directory:
```bash
cd backend
```

2. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Configure Upstox OAuth credentials:
   - Copy `.env.example` to `.env`
   - Update with your actual Upstox client IDs and secrets for both users
   - Set the redirect URI (must match Upstox app settings)

5. Run the backend:
```bash
python main.py
```

The backend will run on `http://localhost:8000`

### Frontend Setup

1. Navigate to frontend directory:
```bash
cd frontend
```

2. Install dependencies:
```bash
npm install
```

3. Run the development server:
```bash
npm run dev
```

The frontend will run on `http://localhost:3000`

## Usage

1. Open `http://localhost:3000` in your browser
2. Click "Login as Samarth" or "Login as Prajwal"
3. Complete OAuth authentication with Upstox
4. You'll be redirected to the Dashboard
5. The system will start polling every 5 seconds and display:
   - Greek signature detection results
   - Aggregated Call/Put Greeks
   - Real-time option chain data

## Project Structure

```
.
├── backend/
│   ├── main.py           # FastAPI app, WebSocket, API endpoints
│   ├── auth.py           # OAuth2 authentication
│   ├── data_fetcher.py   # Upstox API integration, polling
│   ├── signal.py         # Greek signature detection
│   ├── calc.py           # Aggregation calculations
│   ├── database.py       # SQLite database operations
│   └── requirements.txt  # Python dependencies
├── frontend/
│   ├── src/
│   │   ├── pages/
│   │   │   ├── Login.jsx
│   │   │   ├── Dashboard.jsx
│   │   │   ├── Settings.jsx
│   │   │   ├── TradeLogs.jsx
│   │   │   └── OptionChain.jsx
│   │   ├── App.jsx
│   │   └── main.jsx
│   ├── package.json
│   └── vite.config.js
└── README.md
```

## Default Thresholds

- Delta: ≥ 0.20
- Vega: ≥ 0.10
- Theta: ≥ 0.02
- Gamma: ≥ 0.01
- Consecutive Confirmations: 2

These can be modified in the Settings page.

## Important Notes

1. **API Integration**: The Upstox API response structure may need adjustment in `backend/data_fetcher.py` based on the actual API response format.

2. **Instrument Key**: You may need to update the instrument key for NIFTY50 in `backend/data_fetcher.py` based on Upstox's format.

3. **Token Refresh**: Token refresh logic is not fully implemented. You may need to add automatic token refresh when tokens expire.

4. **User Detection**: The frontend currently defaults to 'samarth' for settings/logs. You should implement proper user session management.

## Development

The system follows an iterative development approach:
- Each page is built with its UI first
- Backend endpoints are implemented per page
- Pages are connected before moving to the next

## License

This project is for educational and development purposes.

