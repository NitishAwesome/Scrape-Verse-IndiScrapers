import React from 'react';
import { GitCommit, AlertTriangle, Search, Cpu, RefreshCw, CheckCircle2, Zap } from 'lucide-react';

export default function HealingTimeline({ activeStep = 0, isHealing = false, healingResult = null }) {
  const steps = [
    {
      id: 1,
      title: 'Scrape Initiated',
      desc: 'Collector triggered on target URL',
      icon: GitCommit,
      color: 'cyan',
    },
    {
      id: 2,
      title: 'Selector Failure Detected',
      desc: 'Price element missing from DOM',
      icon: AlertTriangle,
      color: 'red',
    },
    {
      id: 3,
      title: 'DOM Structure Analyzed',
      desc: 'Parsed 14 elements, found candidates',
      icon: Search,
      color: 'violet',
    },
    {
      id: 4,
      title: 'AI Repair Proposed',
      desc: 'Synthesized selector: .current-price',
      icon: Cpu,
      color: 'violet',
    },
    {
      id: 5,
      title: 'Selector Replaced',
      desc: 'Active config dynamically patched',
      icon: RefreshCw,
      color: 'cyan',
    },
    {
      id: 6,
      title: 'Scrape Retried',
      desc: 'Executed pipeline with new selector',
      icon: Zap,
      color: 'emerald',
    },
    {
      id: 7,
      title: 'Validation Passed',
      desc: 'Extracted $49.99 successfully',
      icon: CheckCircle2,
      color: 'emerald',
    },
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
          <h4 className="panel-title">Self-Healing Visual Pipeline</h4>
          {isHealing ? (
            <span className="badge badge-violet animate-pulse">Running Recovery Engine...</span>
          ) : healingResult ? (
            <span className="badge badge-emerald">Healed (Attempt {healingResult.retry_count || 1})</span>
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
                  <Icon size={16} />
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
