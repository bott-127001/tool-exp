import React, { useState } from 'react';
import { Link, Outlet, useNavigate } from 'react-router-dom';
import { useData } from './DataContext';
import { useAuth } from './AuthContext';

function Layout() {
  const { data, connected } = useData();
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
          <Link to="/volatility-permission" onClick={closeMenu}>Volatility</Link>
          <Link to="/direction-asymmetry" onClick={closeMenu}>Direction</Link>
          <Link to="/greeks" onClick={closeMenu}>Greeks</Link>
          <Link to="/option-chain" onClick={closeMenu}>Option Chain</Link>
          <Link to="/rules" onClick={closeMenu}>Rules</Link>
          <Link to="/settings" onClick={closeMenu}>Settings</Link>
          <Link to="/logs" onClick={closeMenu}>Trade Logs</Link>
          
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