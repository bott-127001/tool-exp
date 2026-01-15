import React from 'react'
import { useData } from './DataContext'

function DirectionAsymmetry() {
  const { data } = useData()

  const directionData = data.direction_metrics || {}
  const volatilityData = data.volatility_metrics || {}

  const opening = directionData.opening || {}
  const rea = directionData.rea || {}
  const de = directionData.de
  const directionalState = directionData.directional_state || 'NEUTRAL'
  const directionalInfo = directionData.directional_info || {}

  const volatilityState = volatilityData.market_state

  const hasData =
    data.underlying_price !== null &&
    data.underlying_price !== undefined &&
    Object.keys(directionData).length > 0

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

  const getTradePermission = () => {
    const isDirectional = directionalState !== 'NEUTRAL'
    const hasVolPermission = volatilityState === 'TRANSITION'

    if (isDirectional && hasVolPermission) {
      if (directionalState === 'DIRECTIONAL_BULL') {
        return {
          allowed: true,
          text: 'Trade Allowed: Look ONLY for long-side trades. If volatility permission = ON → buy calls.',
        }
      }
      if (directionalState === 'DIRECTIONAL_BEAR') {
        return {
          allowed: true,
          text: 'Trade Allowed: Look ONLY for short-side trades. If volatility permission = ON → buy puts.',
        }
      }
    }

    return {
      allowed: false,
      text:
        'No Trade: Directional state is neutral or volatility permission is not in TRANSITION. Avoid naked option buying; only manage existing trades.',
    }
  }

  const tradePermission = getTradePermission()

  return (
    <>
      <div className="card">
        <h2>Direction Model</h2>
      </div>

      {hasData ? (
        <>
          {/* Directional State Summary */}
          <div
            className="card"
            style={{
              padding: '20px',
              marginTop: '20px',
              borderRadius: '8px',
              border: `2px solid ${getDirectionalColor(directionalState)}`,
              backgroundColor: getDirectionalColor(directionalState) + '20',
              textAlign: 'center',
            }}
          >
            <h2
              style={{
                color: getDirectionalColor(directionalState),
                margin: '10px 0',
                fontSize: '28px',
              }}
            >
              {getDirectionalLabel(directionalState)}
            </h2>
            <p
              style={{
                fontSize: '16px',
                marginTop: '10px',
                color: '#333',
              }}
            >
              {directionalInfo.reason || 'Waiting for directional assessment...'}
            </p>
          </div>

          {/* Opening Location & Acceptance */}
          <div className="card" style={{ marginTop: '20px' }}>
            <h3>Opening Location & Gap Acceptance</h3>
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
                    <td>
                      <strong>Gap</strong>
                    </td>
                    <td>
                      {opening.gap !== null && opening.gap !== undefined
                        ? opening.gap.toFixed(2)
                        : 'N/A'}
                    </td>
                    <td>Open - Previous Close (when previous day data is available)</td>
                  </tr>
                  <tr>
                    <td>
                      <strong>Gap %</strong>
                    </td>
                    <td>
                      {opening.gap_pct !== null && opening.gap_pct !== undefined
                        ? (opening.gap_pct * 100).toFixed(2) + '%'
                        : 'N/A'}
                    </td>
                    <td>|Gap| / Previous Day Range</td>
                  </tr>
                  <tr>
                    <td>
                      <strong>Acceptance Ratio</strong>
                    </td>
                    <td>
                      {opening.acceptance_ratio !== null &&
                      opening.acceptance_ratio !== undefined
                        ? opening.acceptance_ratio.toFixed(2)
                        : 'N/A'}
                    </td>
                    <td>% of 5-min closes in gap direction after first 30 minutes</td>
                  </tr>
                  <tr>
                    <td>
                      <strong>Opening Bias</strong>
                    </td>
                    <td>{opening.bias || 'NEUTRAL'}</td>
                    <td>BULLISH / BEARISH / NEUTRAL based on gap + acceptance</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>

          {/* REA */}
          <div className="card" style={{ marginTop: '20px' }}>
            <h3>Range Extension Asymmetry (REA)</h3>
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
                    <td>
                      <strong>IB High</strong>
                    </td>
                    <td>
                      {rea.ib_high !== null && rea.ib_high !== undefined
                        ? rea.ib_high.toFixed(2)
                        : 'N/A'}
                    </td>
                    <td>Initial Balance High (first 5 minutes - testing)</td>
                  </tr>
                  <tr>
                    <td>
                      <strong>IB Low</strong>
                    </td>
                    <td>
                      {rea.ib_low !== null && rea.ib_low !== undefined
                        ? rea.ib_low.toFixed(2)
                        : 'N/A'}
                    </td>
                    <td>Initial Balance Low (first 5 minutes - testing)</td>
                  </tr>
                  <tr>
                    <td>
                      <strong>IB Range</strong>
                    </td>
                    <td>
                      {rea.ib_range !== null && rea.ib_range !== undefined
                        ? rea.ib_range.toFixed(2)
                        : 'N/A'}
                    </td>
                    <td>IB High - IB Low</td>
                  </tr>
                  <tr>
                    <td>
                      <strong>RE Up</strong>
                    </td>
                    <td>
                      {rea.re_up !== null && rea.re_up !== undefined
                        ? rea.re_up.toFixed(2)
                        : 'N/A'}
                    </td>
                    <td>Current Day High - IB High (shows N/A until data outside IB window)</td>
                  </tr>
                  <tr>
                    <td>
                      <strong>RE Down</strong>
                    </td>
                    <td>
                      {rea.re_down !== null && rea.re_down !== undefined
                        ? rea.re_down.toFixed(2)
                        : 'N/A'}
                    </td>
                    <td>IB Low - Current Day Low (shows N/A until data outside IB window)</td>
                  </tr>
                  <tr>
                    <td>
                      <strong>REA</strong>
                    </td>
                    <td>
                      {rea.rea !== null && rea.rea !== undefined
                        ? rea.rea.toFixed(2)
                        : 'N/A'}
                    </td>
                    <td>(RE Up - RE Down) / IB Range (shows N/A until data outside IB window)</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>

          {/* Delta Efficiency */}
          <div className="card" style={{ marginTop: '20px' }}>
            <h3>Delta Efficiency (DE)</h3>
            <p>
              <strong>Value:</strong>{' '}
              {de !== null && de !== undefined ? de.toFixed(2) : 'N/A'}
            </p>
            <p style={{ marginTop: '10px', fontSize: '14px' }}>
              Interpretation:{' '}
              <br />
              DE &gt; 0.6 → Trend day, 0.3 – 0.6 → Normal, &lt; 0.3 → Chop / mean-revert.
            </p>
          </div>

          {/* Final Execution Rule */}
          <div
            className="card"
            style={{
              marginTop: '20px',
              padding: '15px',
              backgroundColor: tradePermission.allowed ? '#e6ffed' : '#fff5f5',
              border: `1px solid ${tradePermission.allowed ? '#28a745' : '#dc3545'}`,
            }}
          >
            <h3>Final Execution Rule</h3>
            <p style={{ marginBottom: '10px' }}>
              <strong>Logic:</strong> IF Directional_State ≠ Neutral AND Volatility_Permission
              = TRANSITION THEN Trade ELSE No Trade.
            </p>
            <p>
              <strong>Volatility Permission State:</strong> {volatilityState || 'UNKNOWN'}
            </p>
            <p
              style={{
                marginTop: '10px',
                fontWeight: 'bold',
                color: tradePermission.allowed ? '#155724' : '#721c24',
              }}
            >
              {tradePermission.text}
            </p>
          </div>
        </>
      ) : (
        <div className="card" style={{ marginTop: '20px' }}>
          <p>
            {data.message ||
              'Waiting for direction & asymmetry data... Polling will start automatically.'}
          </p>
        </div>
      )}
    </>
  )
}

export default DirectionAsymmetry


