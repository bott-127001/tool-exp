# Upstox API Integration Notes

## Option Chain API Response Structure

The Upstox API returns option chain data in the following format:

```json
{
  "status": "success",
  "data": [
    {
      "expiry": "2025-02-13",
      "pcr": 7515.3,
      "strike_price": 21100,
      "underlying_key": "NSE_INDEX|Nifty 50",
      "underlying_spot_price": 22976.2,
      "call_options": {
        "instrument_key": "NSE_FO|51059",
        "market_data": {
          "ltp": 2449.9,
          "volume": 0,
          "oi": 750,
          "close_price": 2449.9,
          "bid_price": 1856.65,
          "bid_qty": 1125,
          "ask_price": 1941.65,
          "ask_qty": 1125,
          "prev_oi": 1500
        },
        "option_greeks": {
          "vega": 4.1731,
          "theta": -472.8941,
          "gamma": 0.0001,
          "delta": 0.743,
          "iv": 262.31,
          "pop": 40.56
        }
      },
      "put_options": {
        "instrument_key": "NSE_FO|51060",
        "market_data": {
          "ltp": 0.3,
          "volume": 22315725,
          "oi": 5636475,
          "close_price": 0.35,
          "bid_price": 0.3,
          "bid_qty": 1979400,
          "ask_price": 0.35,
          "ask_qty": 2152500,
          "prev_oi": 5797500
        },
        "option_greeks": {
          "vega": 0.0568,
          "theta": -1.2461,
          "gamma": 0,
          "delta": -0.0013,
          "iv": 50.78,
          "pop": 0.15
        }
      }
    }
  ]
}
```

## API Endpoint

The endpoint used is: `/market-quote/option-chain`

**Note**: You may need to provide:
- `instrument_key`: e.g., `NSE_INDEX|Nifty 50`
- `expiry`: Expiry date (format may vary - check Upstox docs)

Check Upstox API documentation for the exact endpoint format and required parameters.

## Data Normalization

The code now properly converts Upstox response to our internal format:
- Extracts `underlying_spot_price` as the underlying price
- Converts each strike's `call_options` and `put_options` into separate option entries
- Extracts Greeks from `option_greeks` object
- Extracts market data (LTP, OI) from `market_data` object

## Testing

After configuring the endpoint, test with:
1. Start backend
2. Log in with Upstox
3. Check backend console for API responses
4. Verify data appears in dashboard

