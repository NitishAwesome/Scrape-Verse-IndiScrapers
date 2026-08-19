import React from 'react';
import { ArrowRight, CheckCircle2, Cpu, ShieldCheck, Sparkles, Code2 } from 'lucide-react';

export default function SelectorDiffPanel({ repairData }) {
  const {
    oldSelector = '.product-price',
    newSelector = '.current-price',
    confidence = 1.0,
    validationResult = true,
    targetField = 'price',
    reasoning = "Identified replacement DOM element <div> with selector '.current-price' containing value '$49.99'",
  } = repairData || {};

  const confidencePercent = Math.round((confidence || 1.0) * 100);

  return (
    <div className="glass-panel diff-panel">
      <div className="panel-header-row">
        <div className="panel-title-group">
          <Sparkles className="text-violet" size={18} />
          <h4 className="panel-title">AI Selector Repair Comparison</h4>
        </div>
        <div className="badge badge-violet flex-badge">
          <Cpu size={12} /> Autonomous Heuristic Engine
        </div>
      </div>

      <div className="diff-cards-grid">
        <div className="diff-card diff-card-old">
          <div className="diff-card-header">
            <span className="diff-card-label text-red">BROKEN SELECTOR (FAILED)</span>
            <span className="badge badge-red">404 Missing</span>
          </div>
          <div className="diff-code-box mono-font text-red">
            <code>{oldSelector}</code>
          </div>
          <p className="diff-subtext text-muted">
            Failed to resolve on mutated target DOM. Missing required field <span className="text-light">"{targetField}"</span>.
          </p>
        </div>

        <div className="diff-arrow-box">
          <div className="diff-arrow-circle">
            <ArrowRight size={18} className="text-violet" />
          </div>
        </div>

        <div className="diff-card diff-card-new">
          <div className="diff-card-header">
            <span className="diff-card-label text-emerald">AI REPAIRED SELECTOR</span>
            <span className="badge badge-emerald">Active In Memory</span>
          </div>
          <div className="diff-code-box mono-font text-emerald">
            <code>{newSelector}</code>
          </div>
          <p className="diff-subtext text-muted">
            Discovered in updated DOM. Matches currency pattern <span className="text-light">$XX.XX</span>.
          </p>
        </div>
      </div>

      <div className="diff-meta-row">
        <div className="meta-card">
          <span className="meta-card-label">AI Confidence Score</span>
          <div className="confidence-row">
            <div className="confidence-bar-bg">
              <div
                className="confidence-bar-fill"
                style={{ width: `${confidencePercent}%` }}
              ></div>
            </div>
            <span className="mono-font text-violet font-semibold">{confidencePercent}%</span>
          </div>
        </div>

        <div className="meta-card">
          <span className="meta-card-label">Post-Repair Validation</span>
          <div className="validation-status-pill">
            {validationResult ? (
              <span className="badge badge-emerald">
                <CheckCircle2 size={13} /> Validation Passed (100% Valid)
              </span>
            ) : (
              <span className="badge badge-red">Validation Failed</span>
            )}
          </div>
        </div>
      </div>

      {reasoning && (
        <div className="reasoning-box">
          <div className="reasoning-title">
            <Code2 size={14} className="text-cyan" />
            <span>AI Reasoning / DOM Telemetry:</span>
          </div>
          <p className="reasoning-text mono-font text-secondary">{reasoning}</p>
        </div>
      )}
    </div>
  );
}
