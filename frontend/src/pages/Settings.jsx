import React, { useState, useEffect } from 'react'
import axios from 'axios'
import { useAuth } from './AuthContext'

function Settings() {
  const [settings, setSettings] = useState({
    delta_threshold: 0.20,
    vega_threshold: 0.10,
    theta_threshold: 0.02,
    gamma_threshold: 0.01,
    consecutive_confirmations: 2,
    vol_expansion_rv_multiplier: 1.5,
    dir_gap_acceptance_threshold: 0.65,
    dir_acceptance_neutral_threshold: 0.5,
    dir_rea_bull_threshold: 0.3,
    dir_rea_bear_threshold: -0.3,
    dir_rea_neutral_abs_threshold: 0.3,
    dir_de_directional_threshold: 0.5,
    dir_de_neutral_threshold: 0.3
  })
  const { currentUser } = useAuth();
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState('')

  useEffect(() => {
    // Since this is a protected route, we can safely assume currentUser will be available.
    if (currentUser) {
      const loadSettings = async () => {
        try {
          const response = await axios.get(`/api/settings/${currentUser}`);
          if (response.data) {
            setSettings(response.data);
          }
        } catch (error) {
          console.error('Error loading settings:', error);
        }
      };
      loadSettings();
    }
  }, [currentUser]);

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

  const handleDownloadData = async () => {
    try {
      setMessage('Preparing download...');
      const response = await axios.get('/api/export-data', {
        responseType: 'blob', // Important for file download
      });
      
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `market_data_log_${new Date().toISOString().slice(0,10)}.csv`);
      document.body.appendChild(link);
      link.click();
      link.remove();
      setMessage('Download started!');
      setTimeout(() => setMessage(''), 3000);
    } catch (error) {
      console.error('Error downloading data:', error);
      setMessage('Error downloading data.');
    }
  };

  const handleClearData = async () => {
    if (!window.confirm('Are you sure you want to delete ALL collected market data? This cannot be undone.')) {
      return;
    }

    try {
      setMessage('Clearing data...');
      const response = await axios.delete('/api/clear-data');
      setMessage(response.data.message);
      setTimeout(() => setMessage(''), 3000);
    } catch (error) {
      console.error('Error clearing data:', error);
      setMessage('Error clearing data.');
    }
  };

  return (
    <>
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

          <hr style={{ margin: '30px 0', border: '0', borderTop: '1px solid #eee' }} />

          <h3>Volatility-Permission Thresholds</h3>

          <div className="form-group">
            <label htmlFor="vol_expansion_rv_multiplier">Expansion RV Multiplier</label>
            <input
              type="number"
              id="vol_expansion_rv_multiplier"
              name="vol_expansion_rv_multiplier"
              value={settings.vol_expansion_rv_multiplier}
              onChange={handleChange}
              step="0.1"
              min="1"
              required
            />
          </div>

          <hr style={{ margin: '30px 0', border: '0', borderTop: '1px solid #eee' }} />

          <h3>Direction & Asymmetry Thresholds</h3>

          <div className="form-group">
            <label htmlFor="dir_gap_acceptance_threshold">Gap Acceptance Threshold</label>
            <input
              type="number"
              id="dir_gap_acceptance_threshold"
              name="dir_gap_acceptance_threshold"
              value={settings.dir_gap_acceptance_threshold}
              onChange={handleChange}
              step="0.01"
              min="0"
              max="1"
              required
            />
          </div>

          <div className="form-group">
            <label htmlFor="dir_acceptance_neutral_threshold">Acceptance Neutral Threshold</label>
            <input
              type="number"
              id="dir_acceptance_neutral_threshold"
              name="dir_acceptance_neutral_threshold"
              value={settings.dir_acceptance_neutral_threshold}
              onChange={handleChange}
              step="0.01"
              min="0"
              max="1"
              required
            />
          </div>

          <div className="form-group">
            <label htmlFor="dir_rea_bull_threshold">REA Bull Threshold</label>
            <input
              type="number"
              id="dir_rea_bull_threshold"
              name="dir_rea_bull_threshold"
              value={settings.dir_rea_bull_threshold}
              onChange={handleChange}
              step="0.01"
              required
            />
          </div>

          <div className="form-group">
            <label htmlFor="dir_rea_bear_threshold">REA Bear Threshold</label>
            <input
              type="number"
              id="dir_rea_bear_threshold"
              name="dir_rea_bear_threshold"
              value={settings.dir_rea_bear_threshold}
              onChange={handleChange}
              step="0.01"
              required
            />
          </div>

          <div className="form-group">
            <label htmlFor="dir_rea_neutral_abs_threshold">REA Neutral |value| Threshold</label>
            <input
              type="number"
              id="dir_rea_neutral_abs_threshold"
              name="dir_rea_neutral_abs_threshold"
              value={settings.dir_rea_neutral_abs_threshold}
              onChange={handleChange}
              step="0.01"
              required
            />
          </div>

          <div className="form-group">
            <label htmlFor="dir_de_directional_threshold">DE Directional Threshold</label>
            <input
              type="number"
              id="dir_de_directional_threshold"
              name="dir_de_directional_threshold"
              value={settings.dir_de_directional_threshold}
              onChange={handleChange}
              step="0.01"
              min="0"
              max="1"
              required
            />
          </div>

          <div className="form-group">
            <label htmlFor="dir_de_neutral_threshold">DE Neutral Threshold</label>
            <input
              type="number"
              id="dir_de_neutral_threshold"
              name="dir_de_neutral_threshold"
              value={settings.dir_de_neutral_threshold}
              onChange={handleChange}
              step="0.01"
              min="0"
              max="1"
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

        <hr style={{ margin: '30px 0', border: '0', borderTop: '1px solid #eee' }} />
        
        <h3>Data Export</h3>
        <p style={{ marginBottom: '15px', color: '#666' }}>
          Download the collected market data (Greeks, Signals, Prices) for Machine Learning analysis.
        </p>
        <div style={{ display: 'flex', gap: '10px', flexWrap: 'wrap' }}>
          <button 
            onClick={handleDownloadData}
            className="btn"
            style={{ backgroundColor: '#28a745', color: 'white', border: 'none' }}
          >
            Download ML Data (CSV)
          </button>

          <button 
            onClick={handleClearData}
            className="btn"
            style={{ backgroundColor: '#dc3545', color: 'white', border: 'none' }}
          >
            Clear All Data
          </button>
        </div>
      </div>
    </>
  )
}

export default Settings
