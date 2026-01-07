import React, { useState, useEffect } from 'react';
import { Link, Outlet, useNavigate } from 'react-router-dom';
import { useData } from './DataContext';
import { useAuth } from './AuthContext';

function Layout() {
  const { data, connected } = useData();
  const { logout } = useAuth();
  const navigate = useNavigate();
  const [isMenuOpen, setIsMenuOpen] = useState(false);
  const [showPrevDayModal, setShowPrevDayModal] = useState(false);
  const [prevDayModalType, setPrevDayModalType] = useState(null); // 'missing' or 'stale'

  // Check if we need to show the modal
  const needsInput = data?.direction_metrics?.opening?.needs_prev_day_input;
  const isStale = data?.direction_metrics?.opening?.stale_prev_day_data;

  // Show modal when data changes and conditions are met
  useEffect(() => {
    if (needsInput && !showPrevDayModal) {
      setPrevDayModalType('missing');
      setShowPrevDayModal(true);
    } else if (isStale && !showPrevDayModal && !needsInput) {
      setPrevDayModalType('stale');
      setShowPrevDayModal(true);
    }
  }, [needsInput, isStale, showPrevDayModal]);

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

  const closeModal = () => {
    setShowPrevDayModal(false);
  };

  const goToInput = () => {
    setShowPrevDayModal(false);
    navigate('/direction-asymmetry');
  };

  return (
    <div className="container">
      {/* Modal for Previous Day Input Reminder */}
      {showPrevDayModal && (
        <div className="modal-overlay" onClick={closeModal}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3>Previous Day Data Required</h3>
              <button className="modal-close" onClick={closeModal}>×</button>
            </div>
            <div className="modal-body">
              {prevDayModalType === 'missing' ? (
                <>
                  <p><strong>Previous day stats missing.</strong></p>
                  <p>Please input Previous Close and Previous Day Range on the Direction & Asymmetry page so Gap/Gap% and Acceptance can be calculated.</p>
                </>
              ) : (
                <>
                  <p><strong>Previous day stats look stale.</strong></p>
                  <p>Update for today to keep Gap/Gap% accurate.</p>
                </>
              )}
            </div>
            <div className="modal-footer">
              <button className="btn btn-secondary" onClick={closeModal}>
                Cancel
              </button>
              <button className="btn btn-primary" onClick={goToInput}>
                Go to Input
              </button>
            </div>
          </div>
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