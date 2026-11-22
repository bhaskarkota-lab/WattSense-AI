import React, { useState, useEffect } from 'react';
import Navbar from './components/Navbar';
import CustomerPortal from './components/CustomerPortal';
import AdminDashboard from './components/AdminDashboard';
import { AdminAPI, SystemAPI } from './services/api';

export default function App() {
  const [activePortal, setActivePortal] = useState(() => {
    const p = new URLSearchParams(window.location.search).get('portal');
    return p === 'admin' ? 'admin' : 'customer';
  });
  const [health, setHealth] = useState(null);
  const [selectedConsumer, setSelectedConsumer] = useState(() => {
    return new URLSearchParams(window.location.search).get('consumer') || 'CONS-RES-1001';
  });

  useEffect(() => {
    async function checkHealth() {
      try {
        const res = await SystemAPI.getPublicHealth();
        setHealth(res);
      } catch (err) {
        console.warn('API health check error:', err);
        setHealth({ status: 'DEGRADED', database_connected: false });
      }
    }
    checkHealth();
    const interval = setInterval(checkHealth, 30000);
    return () => clearInterval(interval);
  }, []);

  const handleInspectCustomer = (consumerNumber) => {
    setSelectedConsumer(consumerNumber);
    setActivePortal('customer');
  };

  return (
    <div className="app-container">
      <Navbar
        activePortal={activePortal}
        setActivePortal={setActivePortal}
        health={health}
      />

      <main className="main-content">
        {activePortal === 'customer' ? (
          <CustomerPortal
            initialConsumer={selectedConsumer}
            onSwitchToAdmin={() => setActivePortal('admin')}
          />
        ) : (
          <AdminDashboard
            onInspectCustomer={handleInspectCustomer}
          />
        )}
      </main>

      <footer className="footer">
        <div>
          <strong>WattSense AI™</strong> • Smart Electricity Wastage Detection and Consumption Intelligence Platform
        </div>
        <div style={{ marginTop: '4px', fontSize: '0.75rem', color: '#64748b' }}>
          Strict Data Integrity Standards • UCI Appliances Energy Prediction • Chronological Holdout Backtesting • Zero Ground-Truth Conflation
        </div>
      </footer>
    </div>
  );
}
