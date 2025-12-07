import React, { useState, useEffect } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import axios from 'axios'

function TradeLogs() {
  const [logs, setLogs] = useState([])
  const [currentUser, setCurrentUser] = useState('samarth') // Default, should be determined from auth
  const [loading, setLoading] = useState(true)
  const navigate = useNavigate()

  useEffect(() => {
    const loadLogs = async () => {
      try {
        const response = await axios.get(`/api/logs/${currentUser}`)
        if (response.data && response.data.logs) {
          setLogs(response.data.logs)
        }
      } catch (error) {
        console.error('Error loading logs:', error)
        if (error.response?.status === 401) {
          navigate('/login')
        }
      } finally {
        setLoading(false)
      }
    }

    loadLogs()
    
    // Refresh logs every 10 seconds
    const interval = setInterval(loadLogs, 10000)
    return () => clearInterval(interval)
  }, [currentUser, navigate])

  if (loading) {
    return (
      <div className="container">
        <div className="card">
          <p>Loading trade logs...</p>
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
        <h2>Trade Logs</h2>
        <p>Detected signals for: <strong>{currentUser}</strong></p>
        
        {logs.length === 0 ? (
          <p style={{ marginTop: '20px', color: '#666' }}>No signals detected yet.</p>
        ) : (
          <table>
            <thead>
              <tr>
                <th>Timestamp</th>
                <th>Position</th>
                <th>Strike Price</th>
                <th>Strike LTP</th>
                <th>Delta</th>
                <th>Vega</th>
                <th>Theta</th>
                <th>Gamma</th>
              </tr>
            </thead>
            <tbody>
              {logs.map((log, index) => (
                <tr key={index}>
                  <td>{new Date(log.timestamp).toLocaleString()}</td>
                  <td><strong>{log.detected_position}</strong></td>
                  <td>{log.strike_price}</td>
                  <td>{log.strike_ltp?.toFixed(2)}</td>
                  <td>{log.delta.toFixed(4)}</td>
                  <td>{log.vega.toFixed(4)}</td>
                  <td>{log.theta.toFixed(4)}</td>
                  <td>{log.gamma.toFixed(4)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}

export default TradeLogs
