import React from 'react';
import { Play, AlertTriangle, Wand2, Globe, Clock, Layers } from 'lucide-react';

export default function ScraperCard({
  status,
  lastRun,
  latency,
  activeSelector,
  isRunning,
  onRunNormal,
  onSimulateFailure,
  onTriggerHealing,
}) {
  const getStatusBadge = () => {
    switch (status) {
      case 'HEALTHY':
        return <span className="badge badge-emerald"><span className="status-dot status-dot-emerald status-dot-pulse"></span> HEALTHY</span>;
      case 'FAILED':
        return <span className="badge badge-red"><span className="status-dot status-dot-red"></span> SELECTOR BROKEN</span>;
      case 'HEALING':
        return <span className="badge badge-violet"><Wand2 size={12} className="animate-spin" /> HEALING IN PROGRESS</span>;
      default:
        return <span className="badge badge-cyan">READY</span>;
    }
  };

  return (
    <div className="glass-panel scraper-card">
      <div className="scraper-card-header">
        <div className="collector-info-group">
          <div className="collector-avatar">
            <Globe className="text-cyan" size={24} />
          </div>
          <div>
            <div className="collector-title-row">
              <h3 className="collector-title">Amazon / E-Commerce Product Collector</h3>
              {getStatusBadge()}
            </div>
            <div className="collector-meta-row mono-font text-muted">
              <span>ID: c_mock_123456</span>
              <span>•</span>
              <span>Target: mock-site/index.html</span>
              <span>•</span>
              <span className="text-cyan">Active: {activeSelector || '.product-price'}</span>
            </div>
          </div>
        </div>

        <div className="scraper-stats-pill">
          <div className="stat-item">
            <Clock size={14} className="text-secondary" />
            <span className="text-secondary">Last Run:</span>
            <span className="mono-font text-light">{lastRun || 'Just now'}</span>
          </div>
          <div className="stat-item">
            <Layers size={14} className="text-secondary" />
            <span className="text-secondary">Latency:</span>
            <span className="mono-font text-emerald">{latency || '38ms'}</span>
          </div>
        </div>
      </div>

      <div className="scraper-actions-bar">
        <div className="action-buttons-left">
          <button
            className="btn btn-primary"
            onClick={onRunNormal}
            disabled={isRunning}
          >
            <Play size={16} fill="currentColor" />
            <span>Run Normal Scraper</span>
          </button>

          <button
            className="btn btn-danger"
            onClick={onSimulateFailure}
            disabled={isRunning}
          >
            <AlertTriangle size={16} />
            <span>Simulate Failure</span>
          </button>
        </div>

        <div className="action-buttons-right">
          <button
            className="btn btn-ai"
            onClick={onTriggerHealing}
            disabled={isRunning}
          >
            <Wand2 size={16} />
            <span>Demonstrate Self-Healing Recovery</span>
          </button>
        </div>
      </div>
    </div>
  );
}
