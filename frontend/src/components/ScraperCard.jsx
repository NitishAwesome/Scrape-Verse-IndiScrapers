import React from 'react';
import { Play, AlertTriangle, Sparkles, Globe, Clock, Layers, RefreshCw } from 'lucide-react';

export default function ScraperCard({
  status,
  lastRun,
  latency,
  activeSelector,
  isRunning,
  targetUrl,
  onTargetUrlChange,
  collectorId = 'c_mt3d61eq4viqmv3f4',
  scraperMode = 'mock',
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
        return <span className="badge badge-violet"><Sparkles size={12} className="animate-spin" /> HEALING IN PROGRESS</span>;
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
              <h3 className="collector-title">Bright Data Scraper Studio Collector</h3>
              {getStatusBadge()}
            </div>
            <div className="collector-meta-row mono-font text-muted">
              <span>Collector ID: <strong className="text-cyan">{collectorId}</strong></span>
              <span>•</span>
              <span>Mode: <span className={scraperMode === 'brightdata' ? 'text-emerald' : 'text-cyan'}>{scraperMode.toUpperCase()}</span></span>
              <span>•</span>
              <span className="text-cyan">Engine: Auto-Adaptive Batch Recovery</span>
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

      {/* Target URL Input Bar */}
      <div className="target-url-bar">
        <div className="url-input-wrapper">
          <Globe size={15} className="text-muted" />
          <input
            type="text"
            className="url-input mono-font"
            placeholder="Target URL for live scraping (e.g. https://example.com/products)..."
            value={targetUrl || ''}
            onChange={(e) => onTargetUrlChange && onTargetUrlChange(e.target.value)}
          />
        </div>
        <span className="text-xs text-muted">
          {scraperMode === 'brightdata' ? 'Live API Target' : 'Default: mock-site/index.html'}
        </span>
      </div>

      <div className="scraper-actions-bar">
        <div className="action-buttons-left">
          <button
            className={`btn btn-primary ${isRunning ? 'btn-executing' : ''}`}
            onClick={onRunNormal}
            disabled={isRunning}
            title="Execute scraping with current target URL"
          >
            {isRunning ? (
              <>
                <RefreshCw size={16} className="animate-spin text-cyan" />
                <span>Extracting Target Data...</span>
              </>
            ) : (
              <>
                <Play size={16} fill="currentColor" />
                <span>Run Scraper</span>
              </>
            )}
          </button>

          <button
            className="btn btn-danger"
            onClick={onSimulateFailure}
            disabled={isRunning}
            title="Simulate website structure changes breaking selectors"
          >
            <AlertTriangle size={16} />
            <span>Simulate Failure</span>
          </button>
        </div>

        <div className="action-buttons-right">
          <button
            className="btn btn-ai-unified"
            onClick={onTriggerHealing}
            disabled={isRunning}
            title="Execute unified AI self-healing recovery across all broken selectors"
          >
            <Sparkles size={16} className="text-cyan animate-pulse" />
            <span>Self-Healing Recovery</span>
          </button>
        </div>
      </div>
    </div>
  );
}
