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
  const [connectionState, setConnectionState] = useState('disconnected'); // disconnected, connecting, connected, reconnecting
  const [rawChainData, setRawChainData] = useState(null);

  const wsRef = useRef(null);
  const reconnectTimeoutRef = useRef(null);
  const isConnectingRef = useRef(false);
  const connectionIdRef = useRef(0);
  const reconnectAttemptsRef = useRef(0);
  const lastSequenceRef = useRef(-1);

  const connectWebSocket = () => {
    // Prevent duplicate connections
    if (isConnectingRef.current || (wsRef.current && wsRef.current.readyState === WebSocket.OPEN)) {
      console.log('[Context] ⚠️ Connection already exists or in progress, skipping duplicate');
      return;
    }
    
    isConnectingRef.current = true;
    connectionIdRef.current += 1;
    const currentConnectionId = connectionIdRef.current;
    
    const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${wsProtocol}//${window.location.host}/ws`;
    console.log(`[Context] 🔌 Attempting WebSocket connection to ${wsUrl} (ID: ${currentConnectionId})`);

    setConnectionState('connecting');
    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.onopen = () => {
      // Check if this is a stale connection
      if (currentConnectionId !== connectionIdRef.current) {
        console.log(`[Context] ⚠️ Stale connection (ID: ${currentConnectionId}), closing`);
        ws.close();
        return;
      }
      
      isConnectingRef.current = false;
      reconnectAttemptsRef.current = 0;
      setConnected(true);
      setConnectionState('connected');
      console.log(`[Context] ✅ WebSocket connected successfully (ID: ${currentConnectionId})`);
      
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
      // Check if this is a stale connection
      if (currentConnectionId !== connectionIdRef.current) {
        return;
      }
      
      try {
        const newData = JSON.parse(event.data);
        
        // Explicitly handle pong messages from the server heartbeat
        if (newData.type === 'pong') {
          // console.log('[Context] Pong received from server'); // Uncomment for debug
          return; // It's just a heartbeat, no state update needed
        }

        // Validate sequence ordering
        const sequence = newData._sequence ?? -1;
        if (sequence <= lastSequenceRef.current) {
          console.warn(`[Context] ⚠️ Out-of-order data: received ${sequence}, expected > ${lastSequenceRef.current}`);
          return; // Ignore stale/out-of-order data
        }
        
        lastSequenceRef.current = sequence;
        
        // Validate timestamp freshness (reject data older than 1 minute)
        if (newData._poll_timestamp) {
          const pollTime = new Date(newData._poll_timestamp);
          const age = Date.now() - pollTime.getTime();
          if (age > 60000) {
            console.warn(`[Context] ⚠️ Stale data received: ${age}ms old`);
            return;
          }
        }

        setData(newData); // Update state with actual data
        if (newData && newData.timestamp) {
          console.log(`[Context] 📊 Data updated (seq: ${sequence}):`, new Date(newData.timestamp).toLocaleTimeString());
        }
      } catch (error) {
        console.error('[Context] ❌ Error parsing WebSocket data:', error);
      }
    };

    ws.onerror = (error) => {
      // Check if this is a stale connection
      if (currentConnectionId !== connectionIdRef.current) {
        return;
      }
      
      // Only log errors if not already reconnecting to avoid spam
      if (!reconnectTimeoutRef.current) {
        console.warn('[Context] ⚠️ WebSocket connection error (will retry):', error);
      }
      setConnected(false);
      setConnectionState('reconnecting');
    };

    ws.onclose = (event) => {
      // Check if this is a stale connection
      if (currentConnectionId !== connectionIdRef.current) {
        return;
      }
      
      isConnectingRef.current = false;
      setConnected(false);
      setConnectionState('disconnected');
      console.log(`[Context] 📡 WebSocket disconnected - Code: ${event.code}`);

      if (wsRef.current && wsRef.current.keepAliveInterval) {
        clearInterval(wsRef.current.keepAliveInterval);
      }

      // Only reconnect if not a normal closure and not already reconnecting
      if (event.code !== 1000 && !reconnectTimeoutRef.current) {
        setConnectionState('reconnecting');
        
        // Exponential backoff: 3s, 6s, 12s, max 30s
        const delay = Math.min(3000 * Math.pow(2, reconnectAttemptsRef.current), 30000);
        reconnectAttemptsRef.current++;
        
        console.log(`[Context] 🔄 Attempting to reconnect in ${delay/1000}s... (attempt ${reconnectAttemptsRef.current})`);
        reconnectTimeoutRef.current = setTimeout(() => {
          reconnectTimeoutRef.current = null; // Clear the ref after the timeout fires
          // Only reconnect if this is still the current connection attempt
          if (connectionIdRef.current === currentConnectionId) {
            connectWebSocket();
          }
        }, delay);
      }
    };
  };

  useEffect(() => {
    connectWebSocket();

    return () => {
      // Cleanup: cancel reconnection timeout
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
        reconnectTimeoutRef.current = null;
      }
      
      // Cleanup: close WebSocket and clear intervals
      const ws = wsRef.current;
      if (ws) {
        if (wsRef.current && wsRef.current.keepAliveInterval) {
          clearInterval(wsRef.current.keepAliveInterval);
        }
        // Increment connection ID to invalidate any pending reconnections
        connectionIdRef.current += 1;
        isConnectingRef.current = false;
        ws.close();
        wsRef.current = null;
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