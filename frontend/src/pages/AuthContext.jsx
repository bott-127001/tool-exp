import React, { createContext, useState, useContext, useEffect } from 'react';
import axios from 'axios';

const AuthContext = createContext(null);

export function useAuth() {
  return useContext(AuthContext);
}

export function AuthProvider({ children }) {
  const [currentUser, setCurrentUser] = useState(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const checkAuth = async () => {
      try {
        const sessionToken = localStorage.getItem('session_token');
        if (!sessionToken) {
          setCurrentUser(null);
          setIsLoading(false);
          return;
        }

        // Check frontend authentication
        const response = await axios.get('/api/auth/frontend-check', {
          headers: {
            'Authorization': `Bearer ${sessionToken}`
          }
        });

        if (response.data && response.data.authenticated) {
          setCurrentUser(response.data.username);
          localStorage.setItem('currentUser', response.data.username);
        } else {
          // Session invalid, clear it
          localStorage.removeItem('session_token');
          localStorage.removeItem('currentUser');
          setCurrentUser(null);
        }
      } catch (error) {
        console.error('[AuthContext] Auth check failed:', error);
        // Clear invalid session
        localStorage.removeItem('session_token');
        localStorage.removeItem('currentUser');
        setCurrentUser(null);
      } finally {
        setIsLoading(false);
      }
    };

    checkAuth();
  }, []);

  const logout = async () => {
    try {
      const sessionToken = localStorage.getItem('session_token');
      if (sessionToken) {
        await axios.post('/api/auth/frontend-logout', {}, {
          headers: {
            'Authorization': `Bearer ${sessionToken}`
          }
        });
      }
    } catch (error) {
      console.error('[AuthContext] Logout error:', error);
    } finally {
      localStorage.removeItem('session_token');
      localStorage.removeItem('currentUser');
      setCurrentUser(null);
    }
  };

  const value = { currentUser, isLoading, logout };

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  );
}