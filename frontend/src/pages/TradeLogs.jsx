import React, { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import axios from 'axios'
import { useAuth } from './AuthContext' // Import the correct hook

function TradeLogs() {
  const [logs, setLogs] = useState([])
  const { currentUser } = useAuth() // Use the correct hook
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

    if (currentUser) {
      loadLogs()

      // Refresh logs every 10 seconds
      const interval = setInterval(loadLogs, 10000)
      return () => clearInterval(interval)
    } else {
      setLoading(false); // If there's no user, stop loading
    }
  }, [currentUser, navigate])

  return (
    <div className="card">
      <h2>Trade Logs</h2>
      <p>Detected signals for: <strong>{currentUser || '...'}</strong></p>
      
      {loading ? (
        <p>Loading trade logs...</p>
      ) : logs.length === 0 ? (
        <p style={{ marginTop: '20px', color: '#666' }}>No signals detected yet.</p>
      ) : (
        <div className="table-responsive-wrapper">
          <table>
            <thead>
              <tr>
                <th>Timestamp</th>
                <th>Position</th>
                <th>Strike Price</th>
                <th>Strike LTP</th>
              </tr>
            </thead>
            <tbody>
              {logs.map((log, index) => (
                <tr key={index}>
                  <td>{new Date(log.timestamp).toLocaleString()}</td>
                  <td style={{ fontWeight: 'bold' }}>{log.detected_position}</td>
                  <td>{log.strike_price}</td>
                  <td>{log.strike_ltp?.toFixed(2)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

export default TradeLogs
