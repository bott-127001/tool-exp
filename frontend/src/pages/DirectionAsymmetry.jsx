import React, { useEffect, useState } from 'react'
import axios from 'axios'
import { useData } from './DataContext'
import { useAuth } from './AuthContext'

function DirectionAsymmetry() {
  const { data } = useData()
  const { currentUser } = useAuth()

  const [prevDayClose, setPrevDayClose] = useState('')
  const [prevDayRange, setPrevDayRange] = useState('')
  const [saving, setSaving] = useState(false)
  const [saveMsg, setSaveMsg] = useState('')
  const [lastSavedDate, setLastSavedDate] = useState('')

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

  useEffect(() => {
    const fetchPrevDayInputs = async () => {
      if (!currentUser) return
      try {
        const res = await axios.get(`/api/settings/${currentUser}`)
        if (res.data) {
          setPrevDayClose(
            res.data.prev_day_close !== null && res.data.prev_day_close !== undefined
              ? res.data.prev_day_close
              : ''
          )
          setPrevDayRange(
            res.data.prev_day_range !== null && res.data.prev_day_range !== undefined
              ? res.data.prev_day_range
              : ''
          )
          setLastSavedDate(res.data.prev_day_date || '')
        }
      } catch (err) {
        console.error('Failed to load previous-day inputs', err)
      }
    }
    fetchPrevDayInputs()
  }, [currentUser])

  const handleSavePrevDayInputs = async (e) => {
    e.preventDefault()
    if (!currentUser) {
      setSaveMsg('Not logged in. Please re-login.')
      return
    }
    setSaving(true)
    setSaveMsg('')
    try {
      // prev_day_date should be yesterday's date (the date for which the previous day data is valid)
      const yesterday = new Date()
      yesterday.setDate(yesterday.getDate() - 1)
      const prevDayDateIso = yesterday.toISOString().slice(0, 10)
      
      const closeValue = prevDayClose === '' ? null : parseFloat(prevDayClose)
      const rangeValue = prevDayRange === '' ? null : parseFloat(prevDayRange)
      
      await axios.put(`/api/settings/${currentUser}`, {
        prev_day_close: closeValue,
        prev_day_range: rangeValue,
        prev_day_date: prevDayDateIso,
      })
      
      // Update local state immediately
      setLastSavedDate(prevDayDateIso)
      // Ensure values are set correctly (handle empty strings)
      if (closeValue !== null) {
        setPrevDayClose(String(closeValue))
      } else {
        setPrevDayClose('')
      }
      if (rangeValue !== null) {
        setPrevDayRange(String(rangeValue))
      } else {
        setPrevDayRange('')
      }
      
      setSaveMsg('Saved. New values will apply on next data poll.')
      
      // Clear any session storage flags so popup can re-evaluate
      // The key will be different now since data state changed
      Object.keys(sessionStorage).forEach(key => {
        if (key.startsWith('prevDayModalShown_')) {
          sessionStorage.removeItem(key)
        }
      })
      
      setTimeout(() => setSaveMsg(''), 3000)
    } catch (err) {
      console.error('Failed to save previous-day inputs', err)
      setSaveMsg('Error saving. Try again.')
    } finally {
      setSaving(false)
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
        <h2>Direction & Asymmetry Model (Price-Based)</h2>
      </div>

      {/* Previous Day Inputs (Optional) */}
      <div className="card" style={{ marginTop: '20px' }}>
        <h3>Previous Day Inputs (Optional)</h3>
        <p style={{ color: '#666', fontSize: '14px', marginBottom: '10px' }}>
          Hybrid: system uses its data when available; if not, provide values here. These feed into Gap and Gap %.
          Saved values expire daily—please update each day.
        </p>
        <form onSubmit={handleSavePrevDayInputs} style={{ display: 'flex', gap: '12px', flexWrap: 'wrap' }}>
          <div style={{ display: 'flex', flexDirection: 'column' }}>
            <label htmlFor="prev_day_close" style={{ fontWeight: 500, marginBottom: '4px' }}>Previous Day Close</label>
            <input
              id="prev_day_close"
              name="prev_day_close"
              type="number"
              step="0.05"
              min="0"
              value={prevDayClose}
              onChange={(e) => setPrevDayClose(e.target.value)}
              style={{ padding: '8px', minWidth: '160px' }}
            />
          </div>
          <div style={{ display: 'flex', flexDirection: 'column' }}>
            <label htmlFor="prev_day_range" style={{ fontWeight: 500, marginBottom: '4px' }}>Previous Day Range (High - Low)</label>
            <input
              id="prev_day_range"
              name="prev_day_range"
              type="number"
              step="0.05"
              min="0"
              value={prevDayRange}
              onChange={(e) => setPrevDayRange(e.target.value)}
              style={{ padding: '8px', minWidth: '160px' }}
            />
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', justifyContent: 'flex-end' }}>
            <span style={{ fontSize: '12px', color: '#666' }}>
              {lastSavedDate ? `Last saved for: ${lastSavedDate}` : 'No saved date'}
            </span>
          </div>
          <button
            type="submit"
            disabled={saving}
            style={{
              padding: '10px 16px',
              backgroundColor: '#007bff',
              color: 'white',
              border: 'none',
              borderRadius: '4px',
              cursor: 'pointer',
              alignSelf: 'flex-end'
            }}
          >
            {saving ? 'Saving...' : 'Save'}
          </button>
        </form>
        {saveMsg && (
          <p style={{ marginTop: '10px', color: saveMsg.startsWith('Error') ? '#dc3545' : '#28a745' }}>
            {saveMsg}
          </p>
        )}
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
                    <td>Day High - IB High</td>
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
                    <td>IB Low - Day Low</td>
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
                    <td>(RE Up - RE Down) / IB Range</td>
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


