import React, { useEffect, useState } from 'react';
import { Navigate, Outlet } from 'react-router-dom';
import axios from 'axios';

function ProtectedRoute() {
  const [isAuthenticated, setIsAuthenticated] = useState(null);

  useEffect(() => {
    let attempts = 0;
    const maxAttempts = 5;
    const delay = 500; // 0.5 seconds

    const checkAuth = async () => {
      attempts++;
      try {
        const response = await axios.get('/api/auth/current-user');
        if (response.data.user) {
          setIsAuthenticated(true);
          return; // Success!
        }
      } catch (error) {
        console.error(`Auth check attempt ${attempts} failed:`, error);
      }

      if (attempts < maxAttempts) {
        setTimeout(checkAuth, delay);
      } else {
        setIsAuthenticated(false); // All attempts failed
      }
    };

    checkAuth();
  }, []);

  if (isAuthenticated === null) return <div>Loading...</div>; // Or a spinner component
  return isAuthenticated ? <Outlet /> : <Navigate to="/login" />;
}

export default ProtectedRoute;