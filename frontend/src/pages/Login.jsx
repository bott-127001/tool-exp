import React, { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import axios from 'axios'
import { useAuth } from './AuthContext'

function Login() {
  const navigate = useNavigate()
  const { checkAuth } = useAuth()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e) => {
    e.preventDefault()
    console.log('🚀 FORM SUBMITTED!', { username, password: '***' })
    setError('')
    setLoading(true)

    try {
      console.log('🔐 Attempting login for:', username)
      console.log('🌐 Making request to /api/auth/frontend-login')
      const response = await axios.post('/api/auth/frontend-login', {
        username,
        password
      })

      console.log('📥 Login response:', response.data)

      if (response.data && response.data.success) {
        // Store session token
        localStorage.setItem('session_token', response.data.session_token)
        localStorage.setItem('currentUser', response.data.username)
        
        console.log('✅ Login successful, refreshing auth state...')
        // Refresh auth context to update currentUser
        await checkAuth()
        
        console.log('✅ Auth refreshed, redirecting to dashboard...')
        // Redirect to dashboard
        navigate('/dashboard', { replace: true })
      } else {
        console.log('❌ Login failed - no success flag')
        setError('Login failed. Please check your credentials.')
      }
    } catch (err) {
      console.error('❌ Login error:', err)
      console.error('❌ Error response:', err.response?.data)
      setError(err.response?.data?.detail || 'Login failed. Please try again.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={{
      display: 'flex',
      justifyContent: 'center',
      alignItems: 'center',
      minHeight: '100vh',
      background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)'
    }}>
      <div className="card" style={{ minWidth: '400px', textAlign: 'center', padding: '30px' }}>
        <h1 style={{ marginBottom: '30px', color: '#333' }}>
          NIFTY50 Options Signal System
        </h1>
        <p style={{ marginBottom: '30px', color: '#666' }}>
          Sign in to access the dashboard
        </p>
        
        <form onSubmit={handleSubmit}>
          <div style={{ marginBottom: '20px', textAlign: 'left' }}>
            <label style={{ display: 'block', marginBottom: '8px', color: '#333', fontWeight: '500' }}>
              Username
            </label>
            <input
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              required
              style={{
                width: '100%',
                padding: '12px',
                border: '1px solid #ddd',
                borderRadius: '4px',
                fontSize: '16px',
                boxSizing: 'border-box'
              }}
              placeholder="Enter your username"
            />
          </div>
          
          <div style={{ marginBottom: '20px', textAlign: 'left' }}>
            <label style={{ display: 'block', marginBottom: '8px', color: '#333', fontWeight: '500' }}>
              Password
            </label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              style={{
                width: '100%',
                padding: '12px',
                border: '1px solid #ddd',
                borderRadius: '4px',
                fontSize: '16px',
                boxSizing: 'border-box'
              }}
              placeholder="Enter your password"
            />
          </div>
          
          {error && (
            <div style={{
              marginBottom: '20px',
              padding: '12px',
              backgroundColor: '#fee',
              color: '#c33',
              borderRadius: '4px',
              fontSize: '14px'
            }}>
              {error}
            </div>
          )}
          
          <button
            type="submit"
            className="btn btn-primary"
            disabled={loading}
            style={{
              width: '100%',
              padding: '15px',
              fontSize: '16px',
              fontWeight: '600',
              cursor: loading ? 'not-allowed' : 'pointer',
              opacity: loading ? 0.6 : 1
            }}
          >
            {loading ? 'Logging in...' : 'Login'}
          </button>
        </form>
      </div>
    </div>
  )
}

export default Login
