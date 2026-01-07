import React, { useState } from 'react';
import { Link, Outlet, useNavigate } from 'react-router-dom';
import { useData } from './DataContext';
import { useAuth } from './AuthContext';

function Layout() {
  const { connected } = useData();
  const { logout } = useAuth();
  const navigate = useNavigate();
  const [isMenuOpen, setIsMenuOpen] = useState(false);

  const handleLogout = async () => {
    try {
      await logout();
      navigate('/login');
    } catch (error) {
      console.error('Logout error:', error);
      // Still redirect to login even if logout fails
      navigate('/login');
    }
  };

  const toggleMenu = () => {
    setIsMenuOpen(!isMenuOpen);
  };

  const closeMenu = () => {
    setIsMenuOpen(false);
  };

  return (
    <div className="container">
      {data?.direction_metrics?.opening?.needs_prev_day_input && (
        <div
          style={{
            backgroundColor: '#fff3cd',
            border: '1px solid #ffeeba',
            color: '#856404',
            padding: '10px 14px',
            borderRadius: '6px',
            marginBottom: '12px',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            gap: '10px',
            flexWrap: 'wrap'
          }}
        >
          <div>
            <strong>Previous day stats missing.</strong> Please input Previous Close and Previous Day Range on the
            <Link to="/direction-asymmetry" style={{ marginLeft: '6px', color: '#0056b3', fontWeight: 600 }}>
              Direction &amp; Asymmetry
            </Link>{' '}
            page so Gap/Gap% and Acceptance can be calculated.
          </div>
          <button
            onClick={() => navigate('/direction-asymmetry')}
            style={{
              padding: '6px 12px',
              backgroundColor: '#ffc107',
              border: 'none',
              borderRadius: '4px',
              cursor: 'pointer',
              color: '#212529',
              fontWeight: 600
            }}
          >
            Go to Input
          </button>
        </div>
      )}
      {data?.direction_metrics?.opening?.stale_prev_day_data && (
        <div
          style={{
            backgroundColor: '#fff3cd',
            border: '1px solid #ffeeba',
            color: '#856404',
            padding: '10px 14px',
            borderRadius: '6px',
            marginBottom: '12px',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            gap: '10px',
            flexWrap: 'wrap'
          }}
        >
          <div>
            <strong>Previous day stats look stale.</strong> Update for today to keep Gap/Gap% accurate.
          </div>
          <button
            onClick={() => navigate('/direction-asymmetry')}
            style={{
              padding: '6px 12px',
              backgroundColor: '#ffc107',
              border: 'none',
              borderRadius: '4px',
              cursor: 'pointer',
              color: '#212529',
              fontWeight: 600
            }}
          >
            Update Now
          </button>
        </div>
      )}
      <div className="nav">
        <button 
          className="hamburger-btn"
          onClick={toggleMenu}
          aria-label="Toggle menu"
        >
          <span></span>
          <span></span>
          <span></span>
        </button>
        <div className={`nav-links ${isMenuOpen ? 'nav-links-open' : ''}`}>
          <Link to="/dashboard" onClick={closeMenu}>Dashboard</Link>
          <Link to="/rules" onClick={closeMenu}>Rules</Link>
          <Link to="/greeks" onClick={closeMenu}>Greeks</Link>
          <Link to="/volatility-permission" onClick={closeMenu}>Volatility Permission</Link>
          <Link to="/direction-asymmetry" onClick={closeMenu}>Direction & Asymmetry</Link>
          <Link to="/settings" onClick={closeMenu}>Settings</Link>
          <Link to="/logs" onClick={closeMenu}>Trade Logs</Link>
          <Link to="/option-chain" onClick={closeMenu}>Option Chain</Link>
        </div>
        <div className="nav-right">
          <span className={`status-indicator ${connected ? 'status-online' : 'status-offline'}`}></span>
          <span className="status-text">{connected ? 'Connected' : 'Disconnected'}</span>
          <button
            onClick={handleLogout}
            className="logout-btn"
          >
            Logout
          </button>
        </div>
      </div>
      {/* The Outlet component will render the matched child route's component */}
      <Outlet />
    </div>
  );
}

export default Layout;