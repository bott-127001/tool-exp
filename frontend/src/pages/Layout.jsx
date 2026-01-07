import React, { useState, useEffect, useRef, useCallback } from 'react';
import { Link, Outlet, useNavigate, useLocation } from 'react-router-dom';
import { useData } from './DataContext';
import { useAuth } from './AuthContext';
import axios from 'axios';

function Layout() {
  const { data, connected } = useData();
  const { logout, currentUser } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [isMenuOpen, setIsMenuOpen] = useState(false);
  const [showPrevDayModal, setShowPrevDayModal] = useState(false);
  const [prevDayModalType, setPrevDayModalType] = useState(null); // 'missing' or 'stale'
  const [prevDayClose, setPrevDayClose] = useState(null);
  const [prevDayRange, setPrevDayRange] = useState(null);
  const [lastSavedDate, setLastSavedDate] = useState(null);
  const checkIntervalRef = useRef(null);

  // Fetch previous day settings
  useEffect(() => {
    const fetchPrevDaySettings = async () => {
      if (!currentUser) return;
      try {
        const res = await axios.get(`/api/settings/${currentUser}`);
        if (res.data) {
          setPrevDayClose(res.data.prev_day_close);
          setPrevDayRange(res.data.prev_day_range);
          setLastSavedDate(res.data.prev_day_date || null);
        }
      } catch (err) {
        console.error('Failed to load previous-day settings', err);
      }
    };
    fetchPrevDaySettings();
  }, [currentUser]);

  // Check for missing or stale data and show modal
  const checkPrevDayData = useCallback(() => {
    if (!currentUser) return;

    // Check if data is missing
    const hasNoData = !prevDayClose || 
                      !prevDayRange || 
                      prevDayClose === null || 
                      prevDayRange === null ||
                      prevDayClose === '' ||
                      prevDayRange === '' ||
                      !lastSavedDate;
    
    // Check if data is stale (not from yesterday or today)
    let isStale = false;
    if (lastSavedDate && !hasNoData) {
      try {
        const savedDate = new Date(lastSavedDate);
        const today = new Date();
        const yesterday = new Date(today);
        yesterday.setDate(yesterday.getDate() - 1);
        
        // Reset time to compare dates only
        savedDate.setHours(0, 0, 0, 0);
        today.setHours(0, 0, 0, 0);
        yesterday.setHours(0, 0, 0, 0);
        
        // Data is stale if it's not from today or yesterday
        isStale = savedDate.getTime() !== today.getTime() && savedDate.getTime() !== yesterday.getTime();
      } catch (err) {
        // If date parsing fails, consider it stale
        isStale = true;
      }
    }

    // Show modal if data is missing or stale (always check, don't prevent re-showing)
    if (hasNoData) {
      setPrevDayModalType('missing');
      setShowPrevDayModal(true);
    } else if (isStale) {
      setPrevDayModalType('stale');
      setShowPrevDayModal(true);
    }
  }, [currentUser, prevDayClose, prevDayRange, lastSavedDate]);

  // Check on mount and when settings change
  useEffect(() => {
    if (currentUser && (prevDayClose !== null || prevDayRange !== null || lastSavedDate !== null)) {
      checkPrevDayData();
    }
  }, [currentUser, prevDayClose, prevDayRange, lastSavedDate]);

  // Check periodically and on route changes
  useEffect(() => {
    // Check immediately
    if (currentUser) {
      checkPrevDayData();
    }

    // Set up interval to check every 30 seconds
    checkIntervalRef.current = setInterval(() => {
      if (currentUser) {
        checkPrevDayData();
      }
    }, 30000);

    // Cleanup interval on unmount
    return () => {
      if (checkIntervalRef.current) {
        clearInterval(checkIntervalRef.current);
      }
    };
  }, [currentUser, location.pathname, checkPrevDayData]);

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
    // Allow it to show again if conditions are still met
    // The periodic check will re-trigger it if needed
  };

  const goToInput = () => {
    setShowPrevDayModal(false);
    navigate('/direction-asymmetry');
  };

  return (
    <div className="container">
      {/* Modal for Previous Day Input Reminder */}
      {showPrevDayModal && (
        <div className="modal-overlay prev-day-modal-overlay" onClick={closeModal}>
          <div className="modal-content prev-day-modal-content" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header prev-day-modal-header">
              <div className="modal-icon-wrapper">
                {prevDayModalType === 'missing' ? (
                  <span className="modal-icon">⚠️</span>
                ) : (
                  <span className="modal-icon">⏰</span>
                )}
              </div>
              <h3>Previous Day Data Notice</h3>
              <button className="modal-close" onClick={closeModal}>×</button>
            </div>
            <div className="modal-body prev-day-modal-body">
              {prevDayModalType === 'missing' ? (
                <>
                  <p className="modal-message-title"><strong>There is no previous day data.</strong></p>
                  <p className="modal-message-text">Please input Previous Close and Previous Day Range on the Direction & Asymmetry page to enable Gap/Gap% and Acceptance calculations.</p>
                </>
              ) : (
                <>
                  <p className="modal-message-title"><strong>Previous day data is stale.</strong></p>
                  <p className="modal-message-text">You cannot use the same previous day data for 2 days or more. Please update the values for today to keep Gap/Gap% calculations accurate.</p>
                </>
              )}
            </div>
            <div className="modal-footer prev-day-modal-footer">
              <button className="btn btn-secondary" onClick={closeModal}>
                Cancel
              </button>
              <button className="btn btn-primary" onClick={goToInput}>
                Go to Input Page
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