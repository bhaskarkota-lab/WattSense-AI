import React from 'react';
import { Zap, ShieldCheck, UserCheck, BarChart3, Database } from 'lucide-react';

export default function Navbar({ activePortal, setActivePortal, health }) {
  return (
    <header className="navbar">
      <div className="navbar-inner">
        <div className="brand-wrapper">
          <div className="brand-icon">
            <Zap size={22} />
          </div>
          <div>
            <div className="brand-title">
              WattSense AI
              <span className="badge badge-info" style={{ fontSize: '0.68rem', padding: '2px 8px' }}>
                v1.0 Production
              </span>
            </div>
            <div className="brand-subtitle">
              Smart Electricity Wastage Detection & Consumption Intelligence
            </div>
          </div>
        </div>

        <div className="nav-actions">
          <div className="portal-tabs">
            <button
              className={`portal-tab-btn ${activePortal === 'customer' ? 'active' : ''}`}
              onClick={() => setActivePortal('customer')}
            >
              <UserCheck size={16} />
              Customer Portal
            </button>
            <button
              className={`portal-tab-btn ${activePortal === 'admin' ? 'active' : ''}`}
              onClick={() => setActivePortal('admin')}
            >
              <BarChart3 size={16} />
              Admin & Research Hub
            </button>
          </div>

          <div className={`health-badge ${health?.status === 'OPERATIONAL' ? 'operational' : 'degraded'}`}>
            <span className="pulse-dot"></span>
            <span>{health?.status === 'OPERATIONAL' ? 'API Operational' : 'Connecting...'}</span>
          </div>
        </div>
      </div>
    </header>
  );
}
