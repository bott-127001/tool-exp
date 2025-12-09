import React, { useState, useEffect } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import axios from 'axios'
import { useCurrentUser } from './useCurrentUser'

function Settings() {
  const [settings, setSettings] = useState({
    delta_threshold: 0.20,
    vega_threshold: 0.10,
    theta_threshold: 0.02,
    gamma_threshold: 0.01,
    consecutive_confirmations: 2
  })
  const currentUser = useCurrentUser()
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState('')
  const navigate = useNavigate()

  useEffect(() => {
    if (!currentUser) {
      return; // Wait for user to be loaded
    }
    // Load current settings
    const loadSettings = async () => {
      try {
        const response = await axios.get(`/api/settings/${currentUser}`)
        if (response.data) {
          setSettings(response.data)
        }
      } catch (error) {
        console.error('Error loading settings:', error)
        if (error.response?.status === 401) {
          navigate('/login')
        }
      }
    }

    loadSettings()
  }, [currentUser, navigate])

  const handleChange = (e) => {
    const { name, value } = e.target
    setSettings(prev => ({
      ...prev,
      [name]: parseFloat(value) || value
    }))
  }

  const handleSave = async (e) => {
    e.preventDefault()
    setSaving(true)
    setMessage('')

    if (!currentUser) {
      setMessage('Error: No user is logged in.');
      setSaving(false);
      return;
    }

    try {
      const response = await axios.put(
        `/api/settings/${currentUser}`,
        settings
      )
      setMessage('Settings saved successfully!')
      setTimeout(() => setMessage(''), 3000)
    } catch (error) {
      console.error('Error saving settings:', error)
      setMessage('Error saving settings. Please try again.')
    } finally {
      setSaving(false)
    }
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
        <h2>Settings</h2>
        {message && (
          <div style={{
            padding: '10px',
            marginBottom: '20px',
            backgroundColor: message.includes('Error') ? '#f8d7da' : '#d4edda',
            color: message.includes('Error') ? '#721c24' : '#155724',
            borderRadius: '4px'
          }}>
            {message}
          </div>
        )}

        <form onSubmit={handleSave}>
          <div className="form-group">
            <label htmlFor="delta_threshold">Delta Threshold (absolute)</label>
            <input
              type="number"
              id="delta_threshold"
              name="delta_threshold"
              value={settings.delta_threshold}
              onChange={handleChange}
              step="0.01"
              min="0"
              required
            />
          </div>
  
          <div className="form-group">
            <label htmlFor="vega_threshold">Vega Threshold (absolute)</label>
            <input
              type="number"
              id="vega_threshold"
              name="vega_threshold"
              value={settings.vega_threshold}
              onChange={handleChange}
              step="0.01"
              min="0"
              required
            />
          </div>

          <div className="form-group">
            <label htmlFor="theta_threshold">Theta Threshold (absolute)</label>
            <input
              type="number"
              id="theta_threshold"
              name="theta_threshold"
              value={settings.theta_threshold}
              onChange={handleChange}
              step="0.01"
              min="0"
              required
            />
          </div>

          <div className="form-group">
            <label htmlFor="gamma_threshold">Gamma Threshold (absolute)</label>
            <input
              type="number"
              id="gamma_threshold"
              name="gamma_threshold"
              value={settings.gamma_threshold}
              onChange={handleChange}
              step="0.01"
              min="0"
              required
            />
          </div>

          <div className="form-group">
            <label htmlFor="consecutive_confirmations">Consecutive Confirmations</label>
            <input
              type="number"
              id="consecutive_confirmations"
              name="consecutive_confirmations"
              value={settings.consecutive_confirmations}
              onChange={handleChange}
              step="1"
              min="1"
              required
            />
          </div>

          <button
            type="submit"
            className="btn btn-primary"
            disabled={saving}
          >
            {saving ? 'Saving...' : 'Save Settings'}
          </button>
        </form>
      </div>
    </div>
  )
}

export default Settings
