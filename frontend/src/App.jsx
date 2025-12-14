import React from 'react'
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom'
import Login from './pages/Login'
import Dashboard from './pages/Dashboard'
import Settings from './pages/Settings'
import TradeLogs from './pages/TradeLogs'
import OptionChain from './pages/OptionChain'
import Layout from './pages/Layout'
import ProtectedRoute from './pages/ProtectedRoute' // Import the new gatekeeper
import { AuthProvider } from './pages/AuthContext' // Import the new AuthProvider
import { DataProvider } from './pages/DataContext'

function App() {
  return (
    <Router>
      <AuthProvider>
        <DataProvider>
          <Routes>
            <Route path="/login" element={<Login />} />
            <Route element={<ProtectedRoute />}>
              <Route path="/" element={<Layout />}>
                <Route index element={<Navigate to="/dashboard" replace />} />
                <Route path="dashboard" element={<Dashboard />} />
                <Route path="settings" element={<Settings />} />
                <Route path="logs" element={<TradeLogs />} />
                <Route path="option-chain" element={<OptionChain />} />
              </Route>
            </Route>
          </Routes>
        </DataProvider>
      </AuthProvider>
    </Router>
  )
}

export default App
