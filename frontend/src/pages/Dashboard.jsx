import React from 'react'
import { useData } from './DataContext'
import axios from 'axios';

function Dashboard() {
  const { data, connected } = useData();

  const getTickCross = (match) => {
    return match ? <span className="tick">✓</span> : <span className="cross">✗</span>
  }

  // Check if data is available or just placeholder
  const hasData = data.underlying_price !== null && data.underlying_price !== undefined
  const { underlying_price, atm_strike, aggregated_greeks, signals, change_from_baseline, baseline_greeks } = data

  const handleResetBaseline = async () => {
    if (window.confirm('Are you sure you want to reset the baseline for today? A new baseline will be captured on the next data update.')) {
      try {
        const response = await axios.post('/api/reset-baseline');
        alert(response.data.message || 'Baseline reset successfully!');
      } catch (error) {
        console.error('Failed to reset baseline:', error);
        alert('Failed to reset baseline. Please check the console for errors.');
      }
    }
  };

  return (
    <>
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

      <div className="card">
        <h2>Call/Put Aggregation</h2>
        {hasData && aggregated_greeks ? (
        <div className="table-responsive-wrapper">
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
        </div>
        ) : (
          <p>Waiting for aggregation data...</p>
        )}
      </div>

      <div className="card">
        <h2>Change from Baseline</h2>
        {hasData && change_from_baseline ? (
        <div className="table-responsive-wrapper">
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
        </div>
        ) : (
          <p>Waiting for baseline data...</p>
        )}
      </div>

      <div className="card">
        <h2>Baseline Greeks (Captured at Session Start)</h2>
        {hasData && baseline_greeks ? (
        <div className="table-responsive-wrapper">
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
        </div>
        ) : (
          <p>Waiting for baseline data...</p>
        )}
        <button
          onClick={handleResetBaseline}
          style={{
            marginTop: '15px',
            padding: '8px 15px',
            backgroundColor: '#ffc107',
            color: '#212529',
            border: 'none',
            borderRadius: '4px',
            cursor: 'pointer',
            fontWeight: 'bold'
          }}
          title="Clears today's baseline from the database and recaptures it on the next poll. Use this to start a new day."
        >
          Reset Today's Baseline
        </button>
      </div>
    </>
  )
}

export default Dashboard
