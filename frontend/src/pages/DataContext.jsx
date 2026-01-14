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

      // Store the interval ID on the wsRef.current object itself
      // This ensures it's tied to the specific WebSocket instance
      wsRef.current.keepAliveInterval = setInterval(() => {
        if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
          // console.log('[Context] Sending ping to server'); // Uncomment for debug
          wsRef.current.send(JSON.stringify({ type: 'ping' }));
        }
      }, 30000);
    };

    ws.onmessage = (event) => {
      try {
        const newData = JSON.parse(event.data);
        
        // Explicitly handle pong messages from the server heartbeat
        if (newData.type === 'pong') {
          // console.log('[Context] Pong received from server'); // Uncomment for debug
          return; // It's just a heartbeat, no state update needed
        }

        setData(newData); // Update state with actual data
        if (newData && newData.timestamp) {
          console.log('[Context] 📊 Data updated:', new Date(newData.timestamp).toLocaleTimeString());
        }
      } catch (error) {
        console.error('[Context] ❌ Error parsing WebSocket data:', error);
      }
    };

    ws.onerror = (error) => {
      // Only log errors if not already reconnecting to avoid spam
      if (!reconnectTimeoutRef.current) {
        console.warn('[Context] ⚠️ WebSocket connection error (will retry):', error);
      }
      setConnected(false);
    };

    ws.onclose = (event) => {
      setConnected(false);
      console.log(`[Context] 📡 WebSocket disconnected - Code: ${event.code}`);

      if (wsRef.current && wsRef.current.keepAliveInterval) {
        clearInterval(wsRef.current.keepAliveInterval);
      }

      if (event.code !== 1000 && !reconnectTimeoutRef.current) {
        console.log('[Context] 🔄 Attempting to reconnect in 3 seconds...');
        reconnectTimeoutRef.current = setTimeout(() => {
          reconnectTimeoutRef.current = null; // Clear the ref after the timeout fires
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
        if (wsRef.current && wsRef.current.keepAliveInterval) {
          clearInterval(wsRef.current.keepAliveInterval);
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