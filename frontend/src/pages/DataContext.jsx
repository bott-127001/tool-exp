import React, { createContext, useState, useEffect, useRef, useContext } from 'react';

const DataContext = createContext(null);

export function useData() {
  return useContext(DataContext);
}

export function DataProvider({ children }) {
  const [data, setData] = useState({
    underlying_price: null,
    atm_strike: null,
    aggregated_greeks: null,
    signals: null,
    change_from_baseline: null,
    baseline_greeks: null,
    timestamp: null,
    message: "Connecting to server..."
  });
  const [connected, setConnected] = useState(false);
  const [rawChainData, setRawChainData] = useState(null);

  const wsRef = useRef(null);
  const reconnectTimeoutRef = useRef(null);

  const connectWebSocket = () => {
    const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${wsProtocol}//${window.location.host}/ws`;
    console.log(`[Context] 🔌 Attempting WebSocket connection to ${wsUrl}`);

    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.onopen = () => {
      setConnected(true);
      console.log('[Context] ✅ WebSocket connected successfully');
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
        reconnectTimeoutRef.current = null;
      }

      const keepAlive = setInterval(() => {
        if (ws.readyState === WebSocket.OPEN) {
          ws.send(JSON.stringify({ type: 'ping' }));
        }
      }, 30000);
      ws.keepAliveInterval = keepAlive;
    };

    ws.onmessage = (event) => {
      try {
        const newData = JSON.parse(event.data);
        setData(newData);
        // The raw chain data is now part of the main payload from the backend
        // We can extract it if it exists, or fetch separately if needed.
        // For now, we assume the main `data` object is sufficient.
        if (newData && newData.timestamp) {
          console.log('[Context] 📊 Data updated:', new Date(newData.timestamp).toLocaleTimeString());
        }
      } catch (error) {
        console.error('[Context] ❌ Error parsing WebSocket data:', error);
      }
    };

    ws.onerror = (error) => {
      console.error('[Context] ❌ WebSocket error occurred:', error);
      setConnected(false);
    };

    ws.onclose = (event) => {
      setConnected(false);
      console.log(`[Context] 📡 WebSocket disconnected - Code: ${event.code}`);

      if (ws.keepAliveInterval) {
        clearInterval(ws.keepAliveInterval);
      }

      if (event.code !== 1000 && !reconnectTimeoutRef.current) {
        console.log('[Context] 🔄 Attempting to reconnect in 3 seconds...');
        reconnectTimeoutRef.current = setTimeout(() => {
          reconnectTimeoutRef.current = null;
          connectWebSocket();
        }, 3000);
      }
    };
  };

  useEffect(() => {
    connectWebSocket();

    return () => {
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
      const ws = wsRef.current;
      if (ws) {
        if (ws.keepAliveInterval) {
          clearInterval(ws.keepAliveInterval);
        }
        ws.close();
      }
    };
  }, []);

  const value = {
    data,
    connected,
    rawChainData // This can be expanded later if needed
  };

  return <DataContext.Provider value={value}>{children}</DataContext.Provider>;
}