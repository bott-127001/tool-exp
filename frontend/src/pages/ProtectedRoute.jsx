import React from 'react';
import { Navigate, Outlet } from 'react-router-dom';
import { useAuth } from './AuthContext';

function ProtectedRoute() {
  const { currentUser, isLoading } = useAuth();

  if (isLoading) {
    // Display a more user-friendly, centered loading indicator
    return (
      <div style={{
        display: 'flex',
        justifyContent: 'center',
        alignItems: 'center',
        height: '100vh',
        fontSize: '1.2rem',
        color: '#666',
        backgroundColor: '#f4f7f6'
      }}>
        <div>Authenticating...</div>
      </div>
    );
  }
  
  return currentUser ? <Outlet /> : <Navigate to="/login" />;
}

export default ProtectedRoute;