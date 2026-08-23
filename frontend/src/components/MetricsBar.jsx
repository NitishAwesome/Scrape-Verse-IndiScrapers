import React from 'react';
import { Shield, Server, RefreshCw, CheckCircle2, TrendingUp, AlertTriangle } from 'lucide-react';

export default function MetricsBar({ metrics }) {
  const {
    scraperHealth = 'HEALTHY',
    activeScrapers = 1,
    collectorId = 'c_mt3d61eq4viqmv3f4',
    healingEventsCount = 0,
    successRate = '100%',
    isFailed = false,
  } = metrics;

  const isHealthy = scraperHealth === 'HEALTHY' && !isFailed;

  return (
    <div className="metrics-grid">
      <div className="metric-card glass-panel">
        <div className={`metric-icon-box ${isHealthy ? 'bg-emerald-glow' : 'bg-red-glow'}`}>
          {isHealthy ? (
            <Shield className="text-emerald" size={20} />
          ) : (
            <AlertTriangle className="text-red" size={20} />
          )}
        </div>
        <div className="metric-content">
          <span className="metric-label">Scraper Health</span>
          <div className="metric-value-row">
            <span className={`metric-value ${isHealthy ? 'text-emerald' : 'text-red'}`}>
              {isHealthy ? 'HEALTHY' : 'DEGRADED'}
            </span>
            <span className={`badge ${isHealthy ? 'badge-emerald' : 'badge-red'}`}>
              {isHealthy ? 'Active' : 'Broken Rules'}
            </span>
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
            <span className="badge badge-violet">Autonomous Recovery</span>
          </div>
        </div>
      </div>

      <div className="metric-card glass-panel">
        <div className="metric-icon-box bg-emerald-glow">
          <CheckCircle2 className={isHealthy ? 'text-emerald' : 'text-amber'} size={20} />
        </div>
        <div className="metric-content">
          <span className="metric-label">Contract Integrity</span>
          <div className="metric-value-row">
            <span className="metric-value text-light">{isHealthy ? successRate : '0%'}</span>
            <span className={`badge ${isHealthy ? 'badge-emerald' : 'badge-red'} flex-badge`}>
              {isHealthy ? <TrendingUp size={12} /> : <AlertTriangle size={12} />}
              {isHealthy ? '100% Valid' : 'Schema Failed'}
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}
