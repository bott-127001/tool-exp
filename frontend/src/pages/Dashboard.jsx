import React, { useState, useEffect, useRef } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import axios from 'axios'

function Dashboard() {
  const [data, setData] = useState(null)
  const [connected, setConnected] = useState(false)
  const [updateCounter, setUpdateCounter] = useState(0) // Add this
  const wsRef = useRef(null)
  const navigate = useNavigate()
  // Add a ref to track reconnection attempts
  const reconnectTimeoutRef = useRef(null)

  const connectWebSocket = () => {
    // Dynamically construct WebSocket URL
    const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${wsProtocol}//${window.location.host}/ws`;
    console.log(`🔌 Attempting WebSocket connection to ${wsUrl}`);
    
    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.onopen = () => {
      setConnected(true);
      console.log('✅ WebSocket connected successfully');
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
        reconnectTimeoutRef.current = null;
      }

      // Send a ping every 30 seconds to keep the connection alive
      const keepAlive = setInterval(() => {
        if (ws.readyState === WebSocket.OPEN) {
          ws.send(JSON.stringify({ type: 'ping' }));
        }
      }, 30000);
      // Store interval ID to clear it on close
      ws.keepAliveInterval = keepAlive;
    };

    ws.onmessage = (event) => {
      try {
        const newData = JSON.parse(event.data);
        setData(newData);
        if (newData && newData.timestamp) {
          console.log('📊 Data updated:', new Date(newData.timestamp).toLocaleTimeString());
        }
      } catch (error) {
        console.error('❌ Error parsing WebSocket data:', error);
      }
    };

    ws.onerror = (error) => {
      console.error('❌ WebSocket error occurred:', error);
      setConnected(false);
    };

    ws.onclose = (event) => {
      setConnected(false);
      console.log('📡 WebSocket disconnected - Code:', event.code);
      
      // Only reconnect if it wasn't a clean close (code 1000) and not already reconnecting
      if (event.code !== 1000 && !reconnectTimeoutRef.current) {
        console.log('🔄 Attempting to reconnect in 3 seconds...');
        reconnectTimeoutRef.current = setTimeout(() => {
          reconnectTimeoutRef.current = null;
          console.log('🔄 Reconnecting WebSocket...');
          connectWebSocket(); // Reconnect without reloading the page
        }, 3000);
      }

      // Clear the keep-alive interval when the connection closes
      if (ws.keepAliveInterval) {
        clearInterval(ws.keepAliveInterval);
      }
    };
  };

  useEffect(() => {
    // Check authentication and load dashboard data
    const checkAuth = async () => {
      try {
        // Get current user from localStorage or check both (but only once)
        // Try samarth first, then prajwal
        let currentUser = null
        
        const samarthAuth = await axios.get('/api/auth/check/samarth')
          .catch(() => ({ data: { authenticated: false } }))
        
        if (samarthAuth.data?.authenticated) {
          currentUser = 'samarth'
        } else {
          const prajwalAuth = await axios.get('/api/auth/check/prajwal')
            .catch(() => ({ data: { authenticated: false } }))
          
          if (prajwalAuth.data?.authenticated) {
            currentUser = 'prajwal'
          }
        }
        
        // If no user is authenticated, redirect to login
        if (!currentUser) {
          console.log('No user authenticated, redirecting to login')
          navigate('/login')
          return
        }
        
        // Store current user for future use
        localStorage.setItem('currentUser', currentUser)
        
        // Try to get dashboard data
        const response = await axios.get('/api/dashboard')
        if (response.data) {
          setData(response.data)
        }
      } catch (error) {
        console.error('Error loading dashboard:', error)
      }
    }

    checkAuth()

    connectWebSocket();

    return () => {
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current)
      }
      const ws = wsRef.current;
      if (ws) {
        // Clear keep-alive and close connection
        if (ws.keepAliveInterval) {
          clearInterval(ws.keepAliveInterval);
        }
        wsRef.current.close()
      }
    }
  }, []) // Remove navigate dependency to ensure this runs only once

  const getTickCross = (match) => {
    return match ? <span className="tick">✓</span> : <span className="cross">✗</span>
  }

  if (!data) {
    return (
      <div className="container">
        <div className="nav">
          <Link to="/dashboard">Dashboard</Link>
          <Link to="/settings">Settings</Link>
          <Link to="/logs">Trade Logs</Link>
          <Link to="/option-chain">Option Chain</Link>
        </div>
        <div className="card">
          <p>Loading dashboard data...</p>
        </div>
      </div>
    )
  }

  // Check if data is available or just placeholder
  const hasData = data.underlying_price !== null && data.underlying_price !== undefined
  const { underlying_price, atm_strike, aggregated_greeks, signals, change_from_baseline, baseline_greeks } = data

  const handleLogout = async () => {
    try {
      // Get current user from localStorage or check both
      const currentUser = localStorage.getItem('currentUser') || 'samarth'
      
      // Try to logout the current user
      await axios.post(`/api/auth/logout/${currentUser}`)
        .catch(() => {
          // If samarth fails, try prajwal
          return axios.post('/api/auth/logout/prajwal')
        })
      
      // Clear localStorage
      localStorage.removeItem('currentUser')
      
      // Redirect to login
      navigate('/login')
    } catch (error) {
      console.error('Logout error:', error)
      // Still redirect to login even if logout fails
      navigate('/login')
    }
  }

  return (
    <div className="container">
      <div className="nav">
        <Link to="/dashboard">Dashboard</Link>
        <Link to="/settings">Settings</Link>
        <Link to="/logs">Trade Logs</Link>
        <Link to="/option-chain">Option Chain</Link>
        <div style={{ float: 'right' }}>
          <span className={`status-indicator ${connected ? 'status-online' : 'status-offline'}`}></span>
          {connected ? 'Connected' : 'Disconnected'}
          <button 
            onClick={handleLogout}
            style={{
              marginLeft: '15px',
              padding: '5px 15px',
              backgroundColor: '#dc3545',
              color: 'white',
              border: 'none',
              borderRadius: '4px',
              cursor: 'pointer',
              fontSize: '14px'
            }}
          >
            Logout
          </button>
        </div>
      </div>

      <div className="card">
        <h2>Market Data</h2>
        {hasData ? (
          <>
            <p><strong>NIFTY50 Price:</strong> {underlying_price?.toFixed(2)}</p>
            <p><strong>ATM Strike:</strong> {atm_strike}</p>
            <p><strong>Last Updated:</strong> {data.timestamp ? new Date(data.timestamp).toLocaleString() : 'Waiting...'}</p>
            <p style={{ fontSize: '12px', color: '#666' }}>
              Data received at: {new Date().toLocaleTimeString()}
            </p>
          </>
        ) : (
          <p>{data.message || "Waiting for market data... Polling will start automatically."}</p>
        )}
      </div>

      <div className="card">
        <h2>Greek Signature Detector</h2>
        {hasData && signals && signals.length > 0 ? (
        <table>
          <thead>
            <tr>
              <th>Position</th>
              <th>Delta</th>
              <th>Vega</th>
              <th>Theta</th>
              <th>Gamma</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            {signals.map((signal, index) => (
              <tr key={index} style={signal.all_matched ? { backgroundColor: '#d4edda' } : {}}>
                <td><strong>{signal.position}</strong></td>
                <td style={{ textAlign: 'center' }}>
                  {getTickCross(signal.delta.match)}
                </td>
                <td style={{ textAlign: 'center' }}>
                  {getTickCross(signal.vega.match)}
                </td>
                <td style={{ textAlign: 'center' }}>
                  {getTickCross(signal.theta.match)}
                </td>
                <td style={{ textAlign: 'center' }}>
                  {getTickCross(signal.gamma.match)}
                </td>
                <td>
                  {signal.all_matched ? (
                    <span className="tick">Signal Detected!</span>
                  ) : (
                    <span>-</span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        ) : (
          <p>Waiting for signal data...</p>
        )}
      </div>

      <div className="card">
        <h2>Call/Put Aggregation</h2>
        {hasData && aggregated_greeks ? (
        <table>
          <thead>
            <tr>
              <th>Side</th>
              <th>Delta Sum</th>
              <th>Vega Sum</th>
              <th>Theta Sum</th>
              <th>Gamma Sum</th>
              <th>Options Count</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td><strong>Call</strong></td>
              <td>{aggregated_greeks?.call?.delta.toFixed(4)}</td>
              <td>{aggregated_greeks?.call?.vega.toFixed(4)}</td>
              <td>{aggregated_greeks?.call?.theta.toFixed(4)}</td>
              <td>{aggregated_greeks?.call?.gamma.toFixed(4)}</td>
              <td>{aggregated_greeks?.call?.option_count}</td>
            </tr>
            <tr>
              <td><strong>Put</strong></td>
              <td>{aggregated_greeks?.put?.delta.toFixed(4)}</td>
              <td>{aggregated_greeks?.put?.vega.toFixed(4)}</td>
              <td>{aggregated_greeks?.put?.theta.toFixed(4)}</td>
              <td>{aggregated_greeks?.put?.gamma.toFixed(4)}</td>
              <td>{aggregated_greeks?.put?.option_count}</td>
            </tr>
          </tbody>
        </table>
        ) : (
          <p>Waiting for aggregation data...</p>
        )}
      </div>

      <div className="card">
        <h2>Change from Baseline</h2>
        {hasData && change_from_baseline ? (
        <table>
          <thead>
            <tr>
              <th>Side</th>
              <th>Δ Delta</th>
              <th>Δ Vega</th>
              <th>Δ Theta</th>
              <th>Δ Gamma</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td><strong>Call</strong></td>
              <td>{change_from_baseline?.call?.delta.toFixed(4)}</td>
              <td>{change_from_baseline?.call?.vega.toFixed(4)}</td>
              <td>{change_from_baseline?.call?.theta.toFixed(4)}</td>
              <td>{change_from_baseline?.call?.gamma.toFixed(4)}</td>
            </tr>
            <tr>
              <td><strong>Put</strong></td>
              <td>{change_from_baseline?.put?.delta.toFixed(4)}</td>
              <td>{change_from_baseline?.put?.vega.toFixed(4)}</td>
              <td>{change_from_baseline?.put?.theta.toFixed(4)}</td>
              <td>{change_from_baseline?.put?.gamma.toFixed(4)}</td>
            </tr>
          </tbody>
        </table>
        ) : (
          <p>Waiting for baseline data...</p>
        )}
      </div>

      <div className="card">
        <h2>Baseline Greeks (Captured at Session Start)</h2>
        {hasData && baseline_greeks ? (
        <table>
          <thead>
            <tr>
              <th>Side</th>
              <th>Delta Sum</th>
              <th>Vega Sum</th>
              <th>Theta Sum</th>
              <th>Gamma Sum</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td><strong>Call</strong></td>
              <td>{baseline_greeks?.call?.delta.toFixed(4)}</td>
              <td>{baseline_greeks?.call?.vega.toFixed(4)}</td>
              <td>{baseline_greeks?.call?.theta.toFixed(4)}</td>
              <td>{baseline_greeks?.call?.gamma.toFixed(4)}</td>
            </tr>
            <tr>
              <td><strong>Put</strong></td>
              <td>{baseline_greeks?.put?.delta.toFixed(4)}</td>
              <td>{baseline_greeks?.put?.vega.toFixed(4)}</td>
              <td>{baseline_greeks?.put?.theta.toFixed(4)}</td>
              <td>{baseline_greeks?.put?.gamma.toFixed(4)}</td>
            </tr>
          </tbody>
        </table>
        ) : (
          <p>Waiting for baseline data...</p>
        )}
      </div>
    </div>
  )
}

export default Dashboard
