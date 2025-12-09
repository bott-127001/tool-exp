import React from 'react'
import { Link } from 'react-router-dom'
import { useData } from './DataContext'

function OptionChain() {
  const { data } = useData();

  const renderTable = () => {
    if (!data || !data.options || data.options.length === 0) {
      return <p>No option chain data available. Waiting for market data...</p>
    }

    const { options, underlying_price: underlyingPrice, expiry_date } = data;

    // Find ATM strike
    let atmStrike = 0
    let minDiff = Infinity
    // Get unique strikes first
    const strikes = [...new Set(options.map(opt => opt.strike))];
    strikes.forEach(strike => {
      const diff = Math.abs(strike - underlyingPrice)
      if (diff < minDiff) {
        minDiff = diff
        atmStrike = strike
      }
    })

    return (
      <>
        <p><strong>Underlying Price:</strong> {underlyingPrice?.toFixed(2)} | <strong>ATM Strike:</strong> {atmStrike}</p>
        <p><strong>Expiry Date:</strong> {expiry_date}</p>
        <div className="table-responsive-wrapper">
          <table>
            <thead>
              <tr>
                <th colSpan="5" style={{ backgroundColor: '#e9ecef' }}>CALLS</th>
                <th style={{ backgroundColor: '#343a40', color: 'white' }}>Strike</th>
                <th colSpan="5" style={{ backgroundColor: '#e9ecef' }}>PUTS</th>
              </tr>
              <tr>
                <th>OI</th>
                <th>Volume</th>
                <th>IV</th>
                <th>LTP</th>
                <th>Delta</th>
                <th></th>
                <th>Delta</th>
                <th>LTP</th>
                <th>IV</th>
                <th>Volume</th>
                <th>OI</th>
              </tr>
            </thead>
            <tbody>
              {strikes.sort((a, b) => a - b).map((strike) => {
                const call = options.find(o => o.strike === strike && o.type === 'CE');
                const put = options.find(o => o.strike === strike && o.type === 'PE');
                return (
                  <tr key={strike} style={strike === atmStrike ? { backgroundColor: '#fffbe6' } : {}}>
                    <td>{call?.oi}</td>
                    <td>{call?.volume}</td>
                    <td>{call?.iv?.toFixed(2)}</td>
                    <td>{call?.ltp}</td>
                    <td>{call?.delta?.toFixed(2)}</td>
                    <td style={{ fontWeight: 'bold', backgroundColor: '#f8f9fa' }}>{strike}</td>
                    <td>{put?.delta?.toFixed(2)}</td>
                    <td>{put?.ltp}</td>
                    <td>{put?.iv?.toFixed(2)}</td>
                    <td>{put?.volume}</td>
                    <td>{put?.oi}</td>
                  </tr>
                )})}
            </tbody>
          </table>
        </div>
      </>
    )
  }

  return (
    <div className="container">
      <div className="nav">
        <Link to="/dashboard">Dashboard</Link>
        <Link to="/settings">Settings</Link>
        <Link to="/logs">Trade Logs</Link>
        <Link to="/option-chain">Option Chain</Link>
      </div>
      <div className="card">
        <h2>NIFTY50 Option Chain</h2>
        {renderTable()}
      </div>
    </div>
  )
}

export default OptionChain