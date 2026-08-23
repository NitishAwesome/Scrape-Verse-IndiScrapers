import React from 'react';
import { Play, AlertTriangle, Sparkles, Globe, Clock, Layers, RefreshCw, ShieldCheck, Zap } from 'lucide-react';

export default function ScraperCard({
  status,
  lastRun,
  latency,
  activeSelector,
  isRunning,
  targetUrl,
  onTargetUrlChange,
  collectorId = 'c_mt3d61eq4viqmv3f4',
  scraperMode = 'brightdata',
  currentMode = 'LIVE_EXTRACTION', // 'LIVE_EXTRACTION' | 'CONTROLLED_SIMULATION' | 'LIVE_SELF_HEALING'
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
      {/* Top Collector Info */}
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
          <Globe size={15} className="text-cyan" />
          <input
            type="text"
            className="url-input mono-font"
            placeholder="Target URL for live scraping (e.g. https://books.toscrape.com/...)"
            value={targetUrl || ''}
            onChange={(e) => onTargetUrlChange && onTargetUrlChange(e.target.value)}
          />
        </div>
        <span className="badge badge-cyan font-mono text-[10px]">
          {scraperMode === 'brightdata' ? 'LIVE BRIGHT DATA TARGET' : 'LOCAL MOCK SITE'}
        </span>
      </div>

      {/* Active Mode Indicator Strip */}
      <div className="mode-indicator-bar">
        <div className="mode-badge-group">
          <span className="text-xs text-muted">Execution Mode:</span>
          {currentMode === 'CONTROLLED_SIMULATION' ? (
            <span className="mode-badge mode-badge-sim">
              <AlertTriangle size={12} /> Controlled Fault Simulation
            </span>
          ) : currentMode === 'LIVE_SELF_HEALING' ? (
            <span className="mode-badge mode-badge-heal">
              <Sparkles size={12} /> Live Self-Healing Recovery
            </span>
          ) : (
            <span className="mode-badge mode-badge-live">
              <Zap size={12} /> Live Target Extraction
            </span>
          )}
        </div>
        <span className="mode-description">
          {currentMode === 'CONTROLLED_SIMULATION'
            ? 'Active extraction configuration mutated to simulate DOM redesign'
            : currentMode === 'LIVE_SELF_HEALING'
            ? 'Dynamic semantic parsing & candidate confidence ranking active'
            : 'Standard collector execution & schema contract verification'}
        </span>
      </div>

      {/* Controlled Simulation Disclaimer */}
      {currentMode === 'CONTROLLED_SIMULATION' && (
        <div className="simulation-disclaimer-banner">
          <AlertTriangle size={16} className="text-amber shrink-0 mt-0.5" />
          <div>
            <strong>Controlled Failure Simulation Active:</strong> Active extraction selectors have been mutated (.product-title → .product-name, .product-price → .current-price, .product-status → .availability) to demonstrate failure detection. <em>Note: This is a controlled fault test — true adaptability is tested when the self-healing engine parses the live DOM without hardcoded fallbacks.</em>
          </div>
        </div>
      )}

      {/* Action Buttons */}
      <div className="scraper-actions-bar">
        <div className="action-buttons-left">
          <button
            className={`btn btn-primary ${isRunning && currentMode === 'LIVE_EXTRACTION' ? 'btn-executing' : ''}`}
            onClick={onRunNormal}
            disabled={isRunning}
            title="Execute live scraping on target URL"
          >
            {isRunning && currentMode === 'LIVE_EXTRACTION' ? (
              <>
                <RefreshCw size={16} className="animate-spin text-cyan" />
                <span>Extracting Live Data...</span>
              </>
            ) : (
              <>
                <Play size={16} fill="currentColor" />
                <span>Run Scraper (Live)</span>
              </>
            )}
          </button>

          <button
            className="btn btn-danger"
            onClick={onSimulateFailure}
            disabled={isRunning}
            title="Simulate website structure redesign breaking extraction selectors"
          >
            <AlertTriangle size={16} />
            <span>Simulate Failure (Controlled Demo)</span>
          </button>
        </div>

        <div className="action-buttons-right">
          <button
            className="btn btn-ai-unified"
            onClick={onTriggerHealing}
            disabled={isRunning}
            title="Execute dynamic autonomous self-healing recovery across live target DOM"
          >
            <Sparkles size={16} className="text-cyan animate-pulse" />
            <span>Self-Healing Recovery</span>
          </button>
        </div>
      </div>
    </div>
  );
}
