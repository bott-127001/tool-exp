import React, { useState, useEffect } from 'react'
import { useData } from './DataContext'
import { useAuth } from './AuthContext'
import axios from 'axios'

function Dashboard() {
  const { data } = useData()
  const { currentUser } = useAuth()
  const [upstoxLoginStatus, setUpstoxLoginStatus] = useState(null)
  const [triggeringLogin, setTriggeringLogin] = useState(false)
  const [loginMessage, setLoginMessage] = useState('')

  const getTickCross = (match) => {
    return match ? <span className="tick">✓</span> : <span className="cross">✗</span>
  }

  const hasData = data.underlying_price !== null && data.underlying_price !== undefined
  const { signals, underlying_price, atm_strike, timestamp } = data

  // Volatility Permission Data
  const volatilityData = data.volatility_metrics || {}
  const { market_state, state_info } = volatilityData

  // Direction & Asymmetry Data
  const directionData = data.direction_metrics || {}
  const directionalState = directionData.directional_state || 'NEUTRAL'
  const directionalInfo = directionData.directional_info || {}

  const getStateColor = (state) => {
    switch (state) {
      case 'CONTRACTION':
        return '#dc3545' // Red
      case 'TRANSITION':
        return '#ffc107' // Yellow/Orange
      case 'EXPANSION':
        return '#28a745' // Green
      default:
        return '#6c757d' // Gray
    }
  }

  const getStateIcon = (state) => {
    switch (state) {
      case 'CONTRACTION':
        return '🔴'
      case 'TRANSITION':
        return '🟡'
      case 'EXPANSION':
        return '🟢'
      default:
        return '⚪'
    }
  }

  const getDirectionalColor = (state) => {
    switch (state) {
      case 'DIRECTIONAL_BULL':
        return '#28a745'
      case 'DIRECTIONAL_BEAR':
        return '#dc3545'
      default:
        return '#6c757d'
    }
  }

  const getDirectionalLabel = (state) => {
    switch (state) {
      case 'DIRECTIONAL_BULL':
        return 'Directional Day (Bullish)'
      case 'DIRECTIONAL_BEAR':
        return 'Directional Day (Bearish)'
      default:
        return 'Neutral / No-Edge Day'
    }
  }

  // Check Upstox login status on mount and when user changes
  useEffect(() => {
    const checkUpstoxLoginStatus = async () => {
      if (!currentUser) return
      
      try {
        const sessionToken = localStorage.getItem('session_token')
        if (!sessionToken) return
        
        const response = await axios.get('/api/auth/check-upstox-login-status', {
          headers: {
            'Authorization': `Bearer ${sessionToken}`
          }
        })
        
        setUpstoxLoginStatus(response.data)
      } catch (error) {
        console.error('Error checking Upstox login status:', error)
        setUpstoxLoginStatus({
          logged_in_today: false,
          has_token: false,
          token_valid: false,
          message: 'Error checking status'
        })
      }
    }
    
    checkUpstoxLoginStatus()
    // Check every 5 minutes
    const interval = setInterval(checkUpstoxLoginStatus, 5 * 60 * 1000)
    return () => clearInterval(interval)
  }, [currentUser])

  const handleTriggerUpstoxLogin = async () => {
    setTriggeringLogin(true)
    setLoginMessage('')
    
    try {
      const sessionToken = localStorage.getItem('session_token')
      if (!sessionToken) {
        setLoginMessage('Not authenticated. Please login again.')
        setTriggeringLogin(false)
        return
      }
      
      const response = await axios.post('/api/auth/trigger-upstox-login', {}, {
        headers: {
          'Authorization': `Bearer ${sessionToken}`
        }
      })
      
      if (response.data.success) {
        setLoginMessage('✅ Upstox login initiated successfully! Please wait a moment...')
        // Refresh status after a delay
        setTimeout(async () => {
          try {
            const statusResponse = await axios.get('/api/auth/check-upstox-login-status', {
              headers: {
                'Authorization': `Bearer ${sessionToken}`
              }
            })
            setUpstoxLoginStatus(statusResponse.data)
          } catch (error) {
            console.error('Error refreshing status:', error)
          }
        }, 10000) // Wait 10 seconds for login to complete
      } else {
        setLoginMessage('❌ Login failed. Check backend logs for details.')
      }
    } catch (error) {
      console.error('Error triggering Upstox login:', error)
      setLoginMessage(`❌ Error: ${error.response?.data?.detail || error.message}`)
    } finally {
      setTriggeringLogin(false)
    }
  }

  return (
    <>
      <div className="card">
        <h2>Dashboard</h2>
        <p style={{ color: '#666', fontSize: '14px' }}></p>
      </div>

      {/* Upstox Login Status Card */}
      {upstoxLoginStatus && !upstoxLoginStatus.logged_in_today && (
        <div className="card" style={{ 
          marginTop: '20px', 
          backgroundColor: '#fff3cd',
          border: '2px solid #ffc107'
        }}>
          <h2 style={{ color: '#856404', marginBottom: '10px' }}>⚠️ Upstox Login Required</h2>
          <p style={{ color: '#856404', marginBottom: '15px' }}>
            {upstoxLoginStatus.message || 'Automated Upstox login did not happen today at 9:15 AM.'}
          </p>
          {loginMessage && (
            <div style={{
              padding: '10px',
              marginBottom: '15px',
              borderRadius: '4px',
              backgroundColor: loginMessage.includes('✅') ? '#d4edda' : '#f8d7da',
              color: loginMessage.includes('✅') ? '#155724' : '#721c24',
              fontSize: '14px'
            }}>
              {loginMessage}
            </div>
          )}
          <button
            onClick={handleTriggerUpstoxLogin}
            disabled={triggeringLogin}
            style={{
              padding: '12px 24px',
              fontSize: '16px',
              fontWeight: '600',
              backgroundColor: triggeringLogin ? '#6c757d' : '#007bff',
              color: 'white',
              border: 'none',
              borderRadius: '4px',
              cursor: triggeringLogin ? 'not-allowed' : 'pointer',
              opacity: triggeringLogin ? 0.6 : 1
            }}
          >
            {triggeringLogin ? 'Starting Login...' : '🤖 Start Automated Upstox Login'}
          </button>
          <p style={{ 
            fontSize: '12px', 
            color: '#856404', 
            marginTop: '10px',
            fontStyle: 'italic'
          }}>
            This will open a browser window and automatically complete the Upstox OAuth login.
          </p>
        </div>
      )}

      {/* Market Data (mirrors Greeks page) */}
      <div className="card" style={{ marginTop: '20px' }}>
        <h2>Market Data</h2>
        {hasData ? (
          <>
            <p><strong>NIFTY50 Price:</strong> {underlying_price?.toFixed(2)}</p>
            <p><strong>ATM Strike:</strong> {atm_strike}</p>
            <p><strong>Last Updated:</strong> {timestamp ? new Date(timestamp).toLocaleString() : 'Waiting...'}</p>
            <p style={{ fontSize: '12px', color: '#666' }}>
              Data received at: {new Date().toLocaleTimeString()}
            </p>
          </>
        ) : (
          <p>{data.message || "Waiting for market data... Polling will start automatically."}</p>
        )}
      </div>

            {/* Volatility Permission State Card */}
            <div className="card" style={{ marginTop: '20px' }}>
        <h2>Volatility</h2>
        {hasData && market_state ? (
          <div style={{
            padding: '20px',
            marginTop: '15px',
            borderRadius: '8px',
            backgroundColor: getStateColor(market_state) + '20',
            border: `2px solid ${getStateColor(market_state)}`,
            textAlign: 'center'
          }}>
            <div style={{ fontSize: '48px', marginBottom: '10px' }}>
              {getStateIcon(market_state)}
            </div>
            <h3 style={{ 
              color: getStateColor(market_state),
              margin: '10px 0',
              fontSize: '28px'
            }}>
              {market_state}
            </h3>
            <p style={{ 
              fontSize: '16px',
              fontWeight: 'bold',
              margin: '10px 0',
              color: getStateColor(market_state)
            }}>
              {state_info?.action || 'No action specified'}
            </p>
            <p style={{ 
              fontSize: '14px',
              color: '#666',
              marginTop: '10px'
            }}>
              {state_info?.reason || 'No reason provided'}
            </p>
          </div>
        ) : (
          <p>Waiting for volatility permission data...</p>
        )}
      </div>

      {/* Direction & Asymmetry State Card */}
      <div className="card" style={{ marginTop: '20px' }}>
        <h2>Direction</h2>
        {hasData && Object.keys(directionData).length > 0 ? (
          <div style={{
            padding: '20px',
            marginTop: '15px',
            borderRadius: '8px',
            border: `2px solid ${getDirectionalColor(directionalState)}`,
            backgroundColor: getDirectionalColor(directionalState) + '20',
            textAlign: 'center',
          }}>
            <h3 style={{
              color: getDirectionalColor(directionalState),
              margin: '10px 0',
              fontSize: '28px',
            }}>
              {getDirectionalLabel(directionalState)}
            </h3>
            <p style={{
              fontSize: '16px',
              marginTop: '10px',
              color: '#333',
            }}>
              {directionalInfo.reason || 'Waiting for directional assessment...'}
            </p>
          </div>
        ) : (
          <p>Waiting for direction & asymmetry data...</p>
        )}
      </div>

      {/* Greek Signature Table */}
      <div className="card" style={{ marginTop: '20px' }}>
        <h2>Greeks</h2>
        {hasData && signals && signals.length > 0 ? (
          <div className="table-responsive-wrapper">
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
          </div>
        ) : (
          <p>Waiting for signal data...</p>
        )}
      </div>
    </>
  )
}

export default Dashboard
