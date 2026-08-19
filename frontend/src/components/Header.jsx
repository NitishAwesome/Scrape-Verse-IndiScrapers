import React, { useState, useEffect } from 'react';
import { ShieldCheck, Zap, Activity, RefreshCw, Cpu } from 'lucide-react';

export default function Header({ isConnected, onRefresh, isRefreshing }) {
  const [time, setTime] = useState(new Date().toLocaleTimeString());

  useEffect(() => {
    const timer = setInterval(() => {
      setTime(new Date().toLocaleTimeString());
    }, 1000);
    return () => clearInterval(timer);
  }, []);

  return (
    <header className="header-container glass-panel">
      <div className="header-left">
        <div className="logo-icon-wrapper">
          <ShieldCheck className="logo-icon text-emerald" size={28} />
          <div className="logo-glow"></div>
        </div>
        <div className="logo-text-group">
          <div className="logo-title-row">
            <h1 className="logo-title">ScrapeVerse</h1>
            <span className="badge badge-emerald">v2.4 Live</span>
          </div>
          <p className="logo-subtitle">Self-Healing Web Scraping Platform • Powered by Bright Data</p>
        </div>
      </div>

      <div className="header-right">
        <div className="system-pill">
          <Cpu size={14} className="text-violet" />
          <span className="text-secondary">Engine:</span>
          <span className="mono-font text-light">FastAPI + AI Repair</span>
        </div>

        <div className="system-pill">
          <span className={`status-dot ${isConnected ? 'status-dot-emerald status-dot-pulse' : 'status-dot-red'}`}></span>
          <span className="text-secondary">Backend:</span>
          <span className={`mono-font ${isConnected ? 'text-emerald' : 'text-red'}`}>
            {isConnected ? 'ONLINE' : 'DISCONNECTED'}
          </span>
        </div>

        <div className="system-pill mono-font text-muted">
          <Activity size={14} className="text-cyan" />
          <span>{time}</span>
        </div>

        <button
          className="btn btn-secondary btn-icon"
          onClick={onRefresh}
          disabled={isRefreshing}
          title="Refresh Engine Status"
        >
          <RefreshCw size={15} className={isRefreshing ? 'animate-spin' : ''} />
        </button>
      </div>
    </header>
  );
}
