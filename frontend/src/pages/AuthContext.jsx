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
    let attempts = 0;
    const maxAttempts = 10;
    const delay = 500;

    const checkAuth = async () => {
      attempts++;
      try {
        const response = await axios.get('/api/auth/current-user');
        if (response.data && response.data.user) {
          setCurrentUser(response.data.user);
          localStorage.setItem('currentUser', response.data.user); // Keep for legacy/debug if needed
          setIsLoading(false);
          return;
        }
      } catch (error) {
        console.error(`[AuthContext] Auth check attempt ${attempts} failed:`, error);
      }

      if (attempts < maxAttempts) {
        setTimeout(checkAuth, delay);
      } else {
        console.log('[AuthContext] Max attempts reached. User not authenticated.');
        setCurrentUser(null);
        localStorage.removeItem('currentUser');
        setIsLoading(false);
      }
    };

    checkAuth();
  }, []);

  const logout = async () => {
    await axios.post('/api/auth/logout');
    setCurrentUser(null);
    localStorage.removeItem('currentUser');
  };

  const value = { currentUser, isLoading, logout };

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  );
}