import React from 'react'
import { useNavigate } from 'react-router-dom'

function Login() {
  const navigate = useNavigate()

  const handleLogin = (user) => {
    // Redirect to backend OAuth endpoint
    window.location.href = `/api/auth/login?user=${user}`
  }

  return (
    <div style={{
      display: 'flex',
      justifyContent: 'center',
      alignItems: 'center',
      minHeight: '100vh',
      background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)'
    }}>
      <div className="card" style={{ minWidth: '400px', textAlign: 'center' }}>
        <h1 style={{ marginBottom: '30px', color: '#333' }}>
          NIFTY50 Options Signal System
        </h1>
        <p style={{ marginBottom: '30px', color: '#666' }}>
          Sign in with your Upstox account
        </p>
        
        <button
          className="btn btn-primary"
          onClick={() => handleLogin('samarth')}
          style={{ width: '100%', marginBottom: '15px', padding: '15px' }}
        >
          Login as Samarth
        </button>
        
        <button
          className="btn btn-success"
          onClick={() => handleLogin('prajwal')}
          style={{ width: '100%', padding: '15px' }}
        >
          Login as Prajwal
        </button>
      </div>
    </div>
  )
}

export default Login
