import React from 'react'
import { useData } from './DataContext'

function Dashboard() {
  const { data } = useData()

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

  return (
    <>
      <div className="card">
        <h2>Dashboard</h2>
        <p style={{ color: '#666', fontSize: '14px' }}></p>
      </div>

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
