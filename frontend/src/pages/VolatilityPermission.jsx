import React from 'react'
import { useData } from './DataContext'

function VolatilityPermission() {
  const { data } = useData()
  const volatilityData = data.volatility_metrics || {}
  const { 
    rv_current, 
    rv_open_norm, 
    rv_ratio,
    rv_ratio_delta,
    iv_atm, 
    iv_vwap, 
    market_state, 
    state_info,
    current_price,
    open_price,
    price_15min_ago
  } = volatilityData

  const hasData = data.underlying_price !== null && data.underlying_price !== undefined

  const getStateColor = (state) => {
    switch (state) {
      case 'CONTRACTION': return '#dc3545'
      case 'TRANSITION': return '#ffc107'
      case 'EXPANSION': return '#28a745'
      default: return '#6c757d'
    }
  }

  const getStateIcon = (state) => {
    switch (state) {
      case 'CONTRACTION': return '🔴'
      case 'TRANSITION': return '🟡'
      case 'EXPANSION': return '🟢'
      default: return '⚪'
    }
  }

  return (
    <>
      <div className="card">
        <h2>Volatility-Permission Model</h2>
      </div>

      {hasData && market_state ? (
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
            <h2 style={{ color: getStateColor(market_state), margin: '10px 0', fontSize: '32px' }}>
              {market_state}
            </h2>
            <p style={{ fontSize: '18px', fontWeight: 'bold', margin: '10px 0', color: getStateColor(market_state) }}>
              {state_info?.action || 'No action specified'}
            </p>
            <p style={{ fontSize: '14px', color: '#666', marginTop: '10px' }}>
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
                    <td><strong>RV Ratio</strong></td>
                    <td>{rv_ratio != null ? rv_ratio.toFixed(2) : 'N/A'}</td>
                    <td>RV(current) / RV(open-normalized) - Dimensionless ratio</td>
                  </tr>
                  <tr>
                    <td><strong>RV Ratio Delta</strong></td>
                    <td>{rv_ratio_delta != null ? rv_ratio_delta.toFixed(3) : 'N/A'}</td>
                    <td>RV_ratio(t) - RV_ratio(t-1) - Measures acceleration</td>
                  </tr>
                  <tr>
                    <td><strong>RV (current)</strong></td>
                    <td>{rv_current != null ? rv_current.toFixed(2) : 'N/A'}</td>
                    <td>15-minute realized volatility - current movement intensity</td>
                  </tr>
                  <tr>
                    <td><strong>RV (open-normalized)</strong></td>
                    <td>{rv_open_norm != null ? rv_open_norm.toFixed(2) : 'N/A'}</td>
                    <td>Day's average movement speed - normalized by time</td>
                  </tr>
                  <tr>
                    <td><strong>IV (ATM-cluster)</strong></td>
                    <td>{iv_atm != null ? (iv_atm * 100).toFixed(2) + '%' : 'N/A'}</td>
                    <td>Current implied volatility at ATM strike</td>
                  </tr>
                  <tr>
                    <td><strong>IV-VWAP</strong></td>
                    <td>{iv_vwap != null ? (iv_vwap * 100).toFixed(2) + '%' : 'N/A'}</td>
                    <td>Fair volatility price for the day (volume-weighted)</td>
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
                <li>RV Ratio &lt; 0.8 (Configurable)</li>
                <li>IV ≤ IV-VWAP</li>
                <li>Market moving slower than average, option buyers bleed</li>
              </ul>

              <p><strong>🟡 TRANSITION (VALID ENTRY ZONE):</strong></p>
              <ul style={{ marginLeft: '20px', marginBottom: '15px' }}>
                <li>0.8 ≤ RV Ratio ≤ 1.5 (Configurable)</li>
                <li>RV Ratio Delta ≥ Min Acceleration (Configurable)</li>
                <li>IV ≤ IV-VWAP</li>
                <li>Volatility accelerating but IV not repriced yet - BEST TIME TO BUY</li>
              </ul>

              <p><strong>🟢 EXPANSION (DO NOT ENTER FRESH):</strong></p>
              <ul style={{ marginLeft: '20px' }}>
                <li>RV Ratio &gt; 1.5 (Configurable)</li>
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