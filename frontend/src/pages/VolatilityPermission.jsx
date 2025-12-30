import React from 'react'
import { useData } from './DataContext'

function VolatilityPermission() {
  const { data, connected } = useData()
  
  const volatilityData = data.volatility_metrics || {}
  const {
    rv_current,
    rv_open_norm,
    iv_atm,
    iv_vwap,
    market_state,
    state_info,
    current_price,
    open_price,
    price_15min_ago
  } = volatilityData

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

  const hasData = data.underlying_price !== null && data.underlying_price !== undefined

  return (
    <>
      <div className="card">
        <h2>Volatility-Permission Model</h2>
      </div>

      {hasData && volatilityData.market_state ? (
        <>
          <div className="card" style={{
            padding: '20px',
            marginTop: '20px',
            borderRadius: '8px',
            backgroundColor: getStateColor(market_state) + '20',
            border: `2px solid ${getStateColor(market_state)}`,
            textAlign: 'center'
          }}>
            <div style={{ fontSize: '48px', marginBottom: '10px' }}>
              {getStateIcon(market_state)}
            </div>
            <h2 style={{ 
              color: getStateColor(market_state),
              margin: '10px 0',
              fontSize: '32px'
            }}>
              {market_state}
            </h2>
            <p style={{ 
              fontSize: '18px',
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

          <div className="card" style={{ marginTop: '20px' }}>
            <h3>Volatility Metrics</h3>
            <div className="table-responsive-wrapper">
              <table>
                <thead>
                  <tr>
                    <th>Metric</th>
                    <th>Value</th>
                    <th>Description</th>
                  </tr>
                </thead>
                <tbody>
                  <tr>
                    <td><strong>RV (current)</strong></td>
                    <td>{rv_current !== null && rv_current !== undefined ? rv_current.toFixed(2) : 'N/A'}</td>
                    <td>15-minute realized volatility - current movement intensity</td>
                  </tr>
                  <tr>
                    <td><strong>RV (open-normalized)</strong></td>
                    <td>{rv_open_norm !== null && rv_open_norm !== undefined ? rv_open_norm.toFixed(2) : 'N/A'}</td>
                    <td>Day's average movement speed - normalized by time</td>
                  </tr>
                  <tr>
                    <td><strong>IV (ATM-cluster)</strong></td>
                    <td>{iv_atm !== null && iv_atm !== undefined ? (iv_atm * 100).toFixed(2) + '%' : 'N/A'}</td>
                    <td>Current implied volatility at ATM strike</td>
                  </tr>
                  <tr>
                    <td><strong>IV-VWAP</strong></td>
                    <td>{iv_vwap !== null && iv_vwap !== undefined ? (iv_vwap * 100).toFixed(2) + '%' : 'N/A'}</td>
                    <td>Fair volatility price for the day (volume-weighted)</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>

          <div className="card" style={{ marginTop: '20px' }}>
            <h3>Price Information</h3>
            <div className="table-responsive-wrapper">
              <table>
                <thead>
                  <tr>
                    <th>Price Type</th>
                    <th>Value</th>
                  </tr>
                </thead>
                <tbody>
                  <tr>
                    <td><strong>Current Price</strong></td>
                    <td>{current_price !== null && current_price !== undefined ? current_price.toFixed(2) : 'N/A'}</td>
                  </tr>
                  <tr>
                    <td><strong>Open Price</strong></td>
                    <td>{open_price !== null && open_price !== undefined ? open_price.toFixed(2) : 'N/A'}</td>
                  </tr>
                  <tr>
                    <td><strong>Price 15min Ago</strong></td>
                    <td>{price_15min_ago !== null && price_15min_ago !== undefined ? price_15min_ago.toFixed(2) : 'N/A'}</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>

          <div className="card" style={{ marginTop: '20px', padding: '15px' }}>
            <h3>Market State Conditions</h3>
            <div style={{ fontSize: '14px', lineHeight: '1.8' }}>
              <p><strong>🔴 CONTRACTION (NO TRADE):</strong></p>
              <ul style={{ marginLeft: '20px', marginBottom: '15px' }}>
                <li>RV(current) &lt; RV(open-normalized)</li>
                <li>IV ≤ IV-VWAP</li>
                <li>Market moving slower than average, option buyers bleed</li>
              </ul>

              <p><strong>🟡 TRANSITION (VALID ENTRY ZONE):</strong></p>
              <ul style={{ marginLeft: '20px', marginBottom: '15px' }}>
                <li>RV(current) &gt; RV(open-normalized)</li>
                <li>RV(current) is accelerating (increasing)</li>
                <li>IV ≤ IV-VWAP</li>
                <li>Volatility accelerating but IV not repriced yet - BEST TIME TO BUY</li>
              </ul>

              <p><strong>🟢 EXPANSION (DO NOT ENTER FRESH):</strong></p>
              <ul style={{ marginLeft: '20px' }}>
                <li>RV(current) &gt;&gt; RV(open-normalized)</li>
                <li>IV &gt; IV-VWAP</li>
                <li>Volatility already released, options repriced - Manage existing trades only</li>
              </ul>
            </div>
          </div>
        </>
      ) : (
        <div className="card" style={{ marginTop: '20px' }}>
          <p>{data.message || "Waiting for volatility data... Polling will start automatically."}</p>
        </div>
      )}
    </>
  )
}

export default VolatilityPermission

