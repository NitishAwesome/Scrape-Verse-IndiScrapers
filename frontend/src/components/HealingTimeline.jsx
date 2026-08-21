import React from 'react';
import { GitCommit, AlertTriangle, Search, Cpu, RefreshCw, Zap, CheckCircle2, Sparkles } from 'lucide-react';

export default function HealingTimeline({
  activeStep = 0,
  isHealing = false,
  healingResult = null,
}) {
  const steps = [
    { id: 1, title: 'Scrape Started', desc: 'Extraction executed against target DOM', icon: GitCommit, color: 'cyan' },
    { id: 2, title: 'Failures Detected', desc: 'Missing or broken selector fields identified', icon: AlertTriangle, color: 'red' },
    { id: 3, title: 'DOM Analyzed', desc: 'Scanned semantic tree, attributes & text heuristics', icon: Search, color: 'violet' },
    { id: 4, title: 'AI Batch Selector Repair', desc: 'Proposed replacement selectors in one cycle', icon: Cpu, color: 'violet' },
    { id: 5, title: 'Active Config Patched', desc: 'Injected repaired selectors into extraction map', icon: RefreshCw, color: 'cyan' },
    { id: 6, title: 'Extraction Retried', desc: 'Re-executed scraper with repaired selectors', icon: Zap, color: 'emerald' },
    { id: 7, title: 'Validation Passed', desc: 'Zero-downtime recovery verified & complete', icon: CheckCircle2, color: 'emerald' },
  ];

  const getStepStatus = (index) => {
    if (!isHealing && !healingResult && activeStep === 0) return 'idle';
    if (activeStep > index) return 'complete';
    if (activeStep === index) return 'active';
    return 'pending';
  };

  return (
    <div className="glass-panel timeline-panel">
      <div className="panel-header-row">
        <div className="panel-title-group">
          <Zap className="text-violet" size={18} />
          <h4 className="panel-title">
            Self-Healing Autonomous Pipeline
          </h4>
          {isHealing ? (
            <span className="badge badge-violet animate-pulse">Running Recovery Engine...</span>
          ) : healingResult ? (
            <span className="badge badge-emerald">
              <Sparkles size={11} /> Fully Healed (Attempt {healingResult.retry_count || healingResult.attempts || 1})
            </span>
          ) : (
            <span className="badge badge-cyan">Standby / Ready</span>
          )}
        </div>
      </div>

      <div className="timeline-stepper">
        {steps.map((step, idx) => {
          const status = getStepStatus(idx + 1);
          const Icon = step.icon;

          return (
            <div
              key={step.id}
              className={`timeline-step-item ${status === 'active' ? 'step-active' : ''} ${
                status === 'complete' ? 'step-complete' : ''
              }`}
            >
              <div className="step-node-wrapper">
                <div className={`step-node step-node-${step.color} ${status === 'active' ? 'pulse-node' : ''}`}>
                  <Icon size={15} />
                </div>
                {idx < steps.length - 1 && (
                  <div className={`step-connector ${status === 'complete' ? 'connector-filled' : ''}`}></div>
                )}
              </div>

              <div className="step-info">
                <div className="step-title-row">
                  <span className="step-number mono-font">0{step.id}</span>
                  <span className="step-title">{step.title}</span>
                </div>
                <p className="step-desc">{step.desc}</p>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
