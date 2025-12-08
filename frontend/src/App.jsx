import React from 'react'
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom'
import Login from './pages/Login'
import Dashboard from './pages/Dashboard'
import Settings from './pages/Settings'
import TradeLogs from './pages/TradeLogs'
import OptionChain from './pages/OptionChain'
import { DataProvider } from './pages/DataContext'

function App() {
  return (
    <DataProvider>
      <Router>
        <Routes>
          <Route path="/" element={<Navigate to="/login" replace />} />
          <Route path="/login" element={<Login />} />
          <Route path="/dashboard" element={<Dashboard />} />
          <Route path="/settings" element={<Settings />} />
          <Route path="/logs" element={<TradeLogs />} />
          <Route path="/option-chain" element={<OptionChain />} />
        </Routes>
      </Router>
    </DataProvider>
  )
}

export default App
