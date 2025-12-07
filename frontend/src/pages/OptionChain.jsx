import React, { useState, useEffect, useMemo } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import axios from 'axios'

function OptionChain() {
  const [chain, setChain] = useState(null)
  const [loading, setLoading] = useState(true)
  const navigate = useNavigate()

  useEffect(() => {
    const loadChain = async () => {
      try {
        const response = await axios.get('/api/option-chain')
        if (response.data) {
          console.log('Option chain data:', response.data)
          console.log('Expiry date from API:', response.data.expiry_date)
          setChain(response.data)
        }
      } catch (error) {
        if (error.code !== 'ERR_NETWORK' && error.code !== 'ERR_CONNECTION_REFUSED') {
          console.error('Error loading option chain:', error)
        }
        if (error.response?.status === 401) {
          navigate('/login')
        }
      } finally {
        setLoading(false)
      }
    }

    loadChain()
    
    const interval = setInterval(loadChain, 5000)
    return () => clearInterval(interval)
  }, [navigate])

  // Group options by strike and pair calls with puts
  const strikeRows = useMemo(() => {
    if (!chain || !chain.options) return []
    
    const strikeMap = {}
    
    // Group options by strike
    chain.options.forEach(option => {
      const strike = option.strike
      if (!strikeMap[strike]) {
        strikeMap[strike] = { strike, call: null, put: null }
      }
      
      if (option.type === 'CE') {
        strikeMap[strike].call = option
      } else if (option.type === 'PE') {
        strikeMap[strike].put = option
      }
    })
    
    // Convert to array and sort by strike
    return Object.values(strikeMap).sort((a, b) => a.strike - b.strike)
  }, [chain])

  if (loading) {
    return (
      <div className="container">
        <div className="nav">
          <Link to="/dashboard">Dashboard</Link>
          <Link to="/settings">Settings</Link>
          <Link to="/logs">Trade Logs</Link>
          <Link to="/option-chain">Option Chain</Link>
        </div>
        <div className="card">
          <p>Loading option chain...</p>
        </div>
      </div>
    )
  }

  if (!chain || !chain.options || chain.options.length === 0) {
    return (
      <div className="container">
        <div className="nav">
          <Link to="/dashboard">Dashboard</Link>
          <Link to="/settings">Settings</Link>
          <Link to="/logs">Trade Logs</Link>
          <Link to="/option-chain">Option Chain</Link>
        </div>
        <div className="card">
          <p>No option chain data available. Waiting for market data...</p>
        </div>
      </div>
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
        <h2>Option Chain</h2>
        <p><strong>Underlying Price:</strong> {chain.underlying_price?.toFixed(2)}</p>
        <p><strong>Timestamp:</strong> {new Date(chain.timestamp).toLocaleString()}</p>
        <p><strong>Expiry Date:</strong> {chain.expiry_date ? (() => {
          try {
            // Handle YYYY-MM-DD format (e.g., "2025-12-09")
            const dateStr = chain.expiry_date
            if (!dateStr) return 'N/A'
            
            // Parse YYYY-MM-DD format
            const [year, month, day] = dateStr.split('-')
            if (year && month && day) {
              const date = new Date(parseInt(year), parseInt(month) - 1, parseInt(day))
              return date.toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' })
            }
            // Fallback: try standard Date parsing
            const date = new Date(dateStr)
            if (!isNaN(date.getTime())) {
              return date.toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' })
            }
            return dateStr // Return original if all parsing fails
          } catch (e) {
            console.error('Date parsing error:', e, 'Date string:', chain.expiry_date)
            return chain.expiry_date || 'N/A' // Return original if error
          }
        })() : 'N/A'}</p>
        <p><strong>ATM Strike:</strong> {chain.atm_strike}</p>
      </div>

      <div className="card">
        <h3>Options Chain Table</h3>
        <div style={{ overflowX: 'auto', maxHeight: '600px', overflowY: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '12px' }}>
            <thead>
              <tr>
                {/* Call Side Headers */}
                <th colSpan="7" style={{ backgroundColor: '#e3f2fd', textAlign: 'center', border: '1px solid #ddd', padding: '8px' }}>
                  CALL
                </th>
                {/* Strike Price Header */}
                <th style={{ backgroundColor: '#fff9c4', textAlign: 'center', border: '1px solid #ddd', fontWeight: 'bold', padding: '8px' }}>
                  STRIKE
                </th>
                {/* Put Side Headers (inverse order) */}
                <th colSpan="7" style={{ backgroundColor: '#fce4ec', textAlign: 'center', border: '1px solid #ddd', padding: '8px' }}>
                  PUT
                </th>
              </tr>
              <tr>
                {/* Call columns: Volume | OI | Delta | Vega | Theta | Gamma | LTP */}
                <th style={{ border: '1px solid #ddd', padding: '6px', backgroundColor: '#e3f2fd', fontSize: '11px' }}>Volume</th>
                <th style={{ border: '1px solid #ddd', padding: '6px', backgroundColor: '#e3f2fd', fontSize: '11px' }}>OI</th>
                <th style={{ border: '1px solid #ddd', padding: '6px', backgroundColor: '#e3f2fd', fontSize: '11px' }}>Delta</th>
                <th style={{ border: '1px solid #ddd', padding: '6px', backgroundColor: '#e3f2fd', fontSize: '11px' }}>Vega</th>
                <th style={{ border: '1px solid #ddd', padding: '6px', backgroundColor: '#e3f2fd', fontSize: '11px' }}>Theta</th>
                <th style={{ border: '1px solid #ddd', padding: '6px', backgroundColor: '#e3f2fd', fontSize: '11px' }}>Gamma</th>
                <th style={{ border: '1px solid #ddd', padding: '6px', backgroundColor: '#e3f2fd', fontSize: '11px' }}>LTP</th>
                {/* Strike column */}
                <th style={{ border: '1px solid #ddd', padding: '6px', backgroundColor: '#fff9c4', fontWeight: 'bold', fontSize: '11px' }}>Strike</th>
                {/* Put columns (inverse): LTP | Gamma | Theta | Vega | Delta | OI | Volume */}
                <th style={{ border: '1px solid #ddd', padding: '6px', backgroundColor: '#fce4ec', fontSize: '11px' }}>LTP</th>
                <th style={{ border: '1px solid #ddd', padding: '6px', backgroundColor: '#fce4ec', fontSize: '11px' }}>Gamma</th>
                <th style={{ border: '1px solid #ddd', padding: '6px', backgroundColor: '#fce4ec', fontSize: '11px' }}>Theta</th>
                <th style={{ border: '1px solid #ddd', padding: '6px', backgroundColor: '#fce4ec', fontSize: '11px' }}>Vega</th>
                <th style={{ border: '1px solid #ddd', padding: '6px', backgroundColor: '#fce4ec', fontSize: '11px' }}>Delta</th>
                <th style={{ border: '1px solid #ddd', padding: '6px', backgroundColor: '#fce4ec', fontSize: '11px' }}>OI</th>
                <th style={{ border: '1px solid #ddd', padding: '6px', backgroundColor: '#fce4ec', fontSize: '11px' }}>Volume</th>
              </tr>
            </thead>
            <tbody>
              {strikeRows.map((row, index) => {
                const isAtm = row.strike === chain.atm_strike
                return (
                  <tr 
                    key={row.strike} 
                    style={{ 
                      backgroundColor: isAtm ? '#fffde7' : 'transparent',
                      fontWeight: isAtm ? 'bold' : 'normal'
                    }}
                  >
                    {/* Call Side Data: Volume | OI | Delta | Vega | Theta | Gamma | LTP */}
                    <td style={{ border: '1px solid #ddd', padding: '6px', textAlign: 'right', fontSize: '11px' }}>
                      {row.call?.volume ? row.call.volume.toLocaleString() : '-'}
                    </td>
                    <td style={{ border: '1px solid #ddd', padding: '6px', textAlign: 'right', fontSize: '11px' }}>
                      {row.call?.oi ? row.call.oi.toLocaleString() : '-'}
                    </td>
                    <td style={{ border: '1px solid #ddd', padding: '6px', textAlign: 'right', fontSize: '11px' }}>
                      {row.call?.delta !== undefined ? row.call.delta.toFixed(4) : '-'}
                    </td>
                    <td style={{ border: '1px solid #ddd', padding: '6px', textAlign: 'right', fontSize: '11px' }}>
                      {row.call?.vega !== undefined ? row.call.vega.toFixed(4) : '-'}
                    </td>
                    <td style={{ border: '1px solid #ddd', padding: '6px', textAlign: 'right', fontSize: '11px' }}>
                      {row.call?.theta !== undefined ? row.call.theta.toFixed(4) : '-'}
                    </td>
                    <td style={{ border: '1px solid #ddd', padding: '6px', textAlign: 'right', fontSize: '11px' }}>
                      {row.call?.gamma !== undefined ? row.call.gamma.toFixed(4) : '-'}
                    </td>
                    <td style={{ border: '1px solid #ddd', padding: '6px', textAlign: 'right', fontSize: '11px' }}>
                      {row.call?.ltp !== undefined ? row.call.ltp.toFixed(2) : '-'}
                    </td>
                    {/* Strike Price */}
                    <td style={{ 
                      border: '1px solid #ddd', 
                      padding: '6px', 
                      textAlign: 'center', 
                      fontWeight: 'bold',
                      backgroundColor: isAtm ? '#fff9c4' : '#f5f5f5',
                      fontSize: '11px'
                    }}>
                      {row.strike}
                    </td>
                    {/* Put Side Data (inverse): LTP | Gamma | Theta | Vega | Delta | OI | Volume */}
                    <td style={{ border: '1px solid #ddd', padding: '6px', textAlign: 'right', fontSize: '11px' }}>
                      {row.put?.ltp !== undefined ? row.put.ltp.toFixed(2) : '-'}
                    </td>
                    <td style={{ border: '1px solid #ddd', padding: '6px', textAlign: 'right', fontSize: '11px' }}>
                      {row.put?.gamma !== undefined ? row.put.gamma.toFixed(4) : '-'}
                    </td>
                    <td style={{ border: '1px solid #ddd', padding: '6px', textAlign: 'right', fontSize: '11px' }}>
                      {row.put?.theta !== undefined ? row.put.theta.toFixed(4) : '-'}
                    </td>
                    <td style={{ border: '1px solid #ddd', padding: '6px', textAlign: 'right', fontSize: '11px' }}>
                      {row.put?.vega !== undefined ? row.put.vega.toFixed(4) : '-'}
                    </td>
                    <td style={{ border: '1px solid #ddd', padding: '6px', textAlign: 'right', fontSize: '11px' }}>
                      {row.put?.delta !== undefined ? row.put.delta.toFixed(4) : '-'}
                    </td>
                    <td style={{ border: '1px solid #ddd', padding: '6px', textAlign: 'right', fontSize: '11px' }}>
                      {row.put?.oi ? row.put.oi.toLocaleString() : '-'}
                    </td>
                    <td style={{ border: '1px solid #ddd', padding: '6px', textAlign: 'right', fontSize: '11px' }}>
                      {row.put?.volume ? row.put.volume.toLocaleString() : '-'}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}

export default OptionChain
