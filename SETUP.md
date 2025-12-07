# Setup Guide

## Prerequisites

- Python 3.8 or higher
- Node.js 16 or higher
- Upstox API credentials (client ID and secret for both users)

## Quick Start

### 1. Backend Setup

```bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure Environment Variables

Create a `.env` file in the `backend` directory:

```env
UPSTOX_SAMARTH_CLIENT_ID=your_samarth_client_id
UPSTOX_SAMARTH_CLIENT_SECRET=your_samarth_client_secret
UPSTOX_PRAJWAL_CLIENT_ID=your_prajwal_client_id
UPSTOX_PRAJWAL_CLIENT_SECRET=your_prajwal_client_secret
UPSTOX_REDIRECT_URI=http://localhost:8000/auth/callback
```

**Important**: The redirect URI must match exactly what you've configured in your Upstox app settings.

### 3. Start Backend Server

```bash
python main.py
```

The backend will run on `http://localhost:8000`

### 4. Frontend Setup

Open a new terminal:

```bash
cd frontend
npm install
npm run dev
```

The frontend will run on `http://localhost:3000`

## Upstox API Configuration Notes

### Option Chain API

The system expects the Upstox API to return option chain data with Greeks. You may need to adjust the `normalize_option_chain()` function in `backend/data_fetcher.py` based on the actual API response structure.

Current expected structure (adjust as needed):
```json
{
  "data": {
    "underlying_price": 21750.25,
    "options": [
      {
        "strike_price": 21750,
        "instrument_type": "CE",
        "greeks": {
          "delta": 0.32,
          "vega": 0.15,
          "theta": -0.03,
          "gamma": 0.012
        },
        "open_interest": 1200,
        "last_price": 200.5
      }
    ]
  }
}
```

### Instrument Key

You may need to update the instrument key format in `backend/data_fetcher.py` based on Upstox's requirements. The current placeholder uses:
- Format: `NSE_INDEX|Nifty 50`

## Database

The SQLite database (`options_signals.db`) will be created automatically on first run. It contains:
- `users`: OAuth tokens
- `user_settings`: Threshold configurations per user
- `trade_logs`: Detected signals

## Testing

1. Start both backend and frontend
2. Open `http://localhost:3000`
3. Click login button for either user
4. Complete OAuth flow
5. Dashboard should display live data (if API is configured correctly)

## Troubleshooting

### "No data available yet"
- Check if OAuth tokens are stored in database
- Verify Upstox API credentials
- Check backend logs for API errors

### "WebSocket disconnected"
- Ensure backend is running
- Check CORS settings in `backend/main.py`

### API Response Errors
- Verify the API response structure matches expectations
- Update `normalize_option_chain()` function accordingly
- Check Upstox API documentation for exact response format

