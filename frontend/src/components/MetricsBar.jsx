import React from 'react';
import { Shield, Server, RefreshCw, CheckCircle2, TrendingUp } from 'lucide-react';

export default function MetricsBar({ metrics }) {
  const {
    scraperHealth = 'HEALTHY',
    activeScrapers = 1,
    collectorId = 'c_mt3d61eq4viqmv3f4',
    healingEventsCount = 0,
    successRate = '100%',
  } = metrics;

  return (
    <div className="metrics-grid">
      <div className="metric-card glass-panel">
        <div className="metric-icon-box bg-emerald-glow">
          <Shield className="text-emerald" size={20} />
        </div>
        <div className="metric-content">
          <span className="metric-label">Scraper Health</span>
          <div className="metric-value-row">
            <span className="metric-value text-emerald">{scraperHealth}</span>
            <span className="badge badge-emerald">99.8%</span>
          </div>
        </div>
      </div>

      <div className="metric-card glass-panel">
        <div className="metric-icon-box bg-cyan-glow">
          <Server className="text-cyan" size={20} />
        </div>
        <div className="metric-content">
          <span className="metric-label">Active Collectors</span>
          <div className="metric-value-row">
            <span className="metric-value text-light">{activeScrapers}</span>
            <span className="metric-subtext text-cyan">{collectorId}</span>
          </div>
        </div>
      </div>

      <div className="metric-card glass-panel">
        <div className="metric-icon-box bg-violet-glow">
          <RefreshCw className="text-violet" size={20} />
        </div>
        <div className="metric-content">
          <span className="metric-label">Auto-Healed Incidents</span>
          <div className="metric-value-row">
            <span className="metric-value text-violet">{healingEventsCount}</span>
            <span className="badge badge-violet">Zero Downtime</span>
          </div>
        </div>
      </div>

      <div className="metric-card glass-panel">
        <div className="metric-icon-box bg-amber-glow">
          <CheckCircle2 className="text-emerald" size={20} />
        </div>
        <div className="metric-content">
          <span className="metric-label">Healing Success Rate</span>
          <div className="metric-value-row">
            <span className="metric-value text-light">{successRate}</span>
            <span className="badge badge-emerald flex-badge">
              <TrendingUp size={12} /> Optimal
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}
