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
  const [settingsLoaded, setSettingsLoaded] = useState(false);
  const checkIntervalRef = useRef(null);
  const fetchSettingsRef = useRef(null);

  // Fetch previous day settings
  const fetchPrevDaySettings = useCallback(async () => {
    if (!currentUser) return;
    try {
      const res = await axios.get(`/api/settings/${currentUser}`);
      if (res.data) {
        setPrevDayClose(res.data.prev_day_close);
        setPrevDayRange(res.data.prev_day_range);
        setLastSavedDate(res.data.prev_day_date || null);
        setSettingsLoaded(true);
      }
    } catch (err) {
      console.error('Failed to load previous-day settings', err);
      setSettingsLoaded(true); // Mark as loaded even on error
    }
  }, [currentUser]);

  // Initial fetch and refetch on user change
  useEffect(() => {
    fetchPrevDaySettings();
  }, [fetchPrevDaySettings]);

  // Refetch settings when navigating away from direction-asymmetry page (after potential save)
  const prevPathRef = useRef(location.pathname);
  useEffect(() => {
    // If we navigated away from direction-asymmetry page, refetch settings
    if (prevPathRef.current === '/direction-asymmetry' && location.pathname !== '/direction-asymmetry') {
      // Small delay to ensure save has completed
      setTimeout(() => {
        fetchPrevDaySettings();
      }, 500);
    }
    prevPathRef.current = location.pathname;
  }, [location.pathname, fetchPrevDaySettings]);

  // Check for missing or stale data and show modal (only once per session)
  const checkPrevDayData = useCallback(() => {
    if (!currentUser || !settingsLoaded) return;

    // Check if data is missing
    const hasNoData = !prevDayClose || 
                      !prevDayRange || 
                      prevDayClose === null || 
                      prevDayRange === null ||
                      prevDayClose === '' ||
                      prevDayRange === '' ||
                      !lastSavedDate;
    
    // Check if data is stale (not from yesterday - matching backend logic)
    let isStale = false;
    if (lastSavedDate && !hasNoData) {
      try {
        const savedDate = new Date(lastSavedDate);
        const today = new Date();
        const yesterday = new Date(today);
        yesterday.setDate(yesterday.getDate() - 1);
        
        // Reset time to compare dates only
        savedDate.setHours(0, 0, 0, 0);
        yesterday.setHours(0, 0, 0, 0);
        
        // Data is stale if it's not from yesterday (matching backend expectation)
        // The prev_day_date should represent yesterday's date
        isStale = savedDate.getTime() !== yesterday.getTime();
      } catch (err) {
        // If date parsing fails, consider it stale
        isStale = true;
      }
    }

    // Create a unique key for this data state
    const dataStateKey = `${hasNoData ? 'missing' : isStale ? 'stale' : 'valid'}_${lastSavedDate || 'none'}`;
    const sessionKey = `prevDayModalShown_${dataStateKey}`;
    
    // Check if we've already shown the modal for this data state in this session
    const alreadyShown = sessionStorage.getItem(sessionKey) === 'true';

    // Only show modal if data is missing or stale AND we haven't shown it for this state yet
    if ((hasNoData || isStale) && !alreadyShown) {
      setPrevDayModalType(hasNoData ? 'missing' : 'stale');
      setShowPrevDayModal(true);
      // Mark as shown for this data state
      sessionStorage.setItem(sessionKey, 'true');
    } else if (!hasNoData && !isStale) {
      // If data is valid, clear any session flags
      sessionStorage.removeItem(sessionKey);
    }
  }, [currentUser, prevDayClose, prevDayRange, lastSavedDate, settingsLoaded]);

  // Check when settings are loaded or change
  useEffect(() => {
    if (currentUser && settingsLoaded) {
      checkPrevDayData();
    }
  }, [currentUser, prevDayClose, prevDayRange, lastSavedDate, settingsLoaded, checkPrevDayData]);

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