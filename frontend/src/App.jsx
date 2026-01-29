import React from 'react'
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom'
import Login from './pages/Login'
import Dashboard from './pages/Dashboard'
import Greeks from './pages/Greeks'
import Settings from './pages/Settings'
import TradeLogs from './pages/TradeLogs'
import OptionChain from './pages/OptionChain'
import VolatilityPermission from './pages/VolatilityPermission'
import DirectionAsymmetry from './pages/DirectionAsymmetry'
import Rules from './pages/Rules'
import Layout from './pages/Layout'
import ProtectedRoute from './pages/ProtectedRoute' // Import the new gatekeeper
import { AuthProvider } from './pages/AuthContext' // Import the new AuthProvider
import { DataProvider } from './pages/DataContext'

function App() {
  return (
    <Router future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
      <AuthProvider>
        <DataProvider>
          <Routes>
            <Route path="/login" element={<Login />} />
            <Route element={<ProtectedRoute />}>
              <Route path="/" element={<Layout />}>
                <Route index element={<Navigate to="/dashboard" replace />} />
                <Route path="dashboard" element={<Dashboard />} />
                <Route path="greeks" element={<Greeks />} />
                <Route path="settings" element={<Settings />} />
                <Route path="logs" element={<TradeLogs />} />
                <Route path="option-chain" element={<OptionChain />} />
                <Route path="volatility-permission" element={<VolatilityPermission />} />
                <Route path="direction-asymmetry" element={<DirectionAsymmetry />} />
                <Route path="rules" element={<Rules />} />
              </Route>
            </Route>
          </Routes>
        </DataProvider>
      </AuthProvider>
    </Router>
  )
}

export default App
