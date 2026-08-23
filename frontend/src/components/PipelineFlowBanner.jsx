import React from 'react';
import { Globe, Cpu, Database, ShieldCheck, HeartPulse, ArrowRight } from 'lucide-react';

export default function PipelineFlowBanner({ status, recordCount = 0, isHealing = false, targetUrl = '' }) {
  const isHealthy = status === 'HEALTHY';
  const isFailed = status === 'FAILED';

  const displayTarget = targetUrl 
    ? (targetUrl.replace(/^https?:\/\//, '').split('/')[0] + '...')
    : 'mock-site/index.html';

  const steps = [
    {
      id: 'target',
      label: 'TARGET WEBSITE',
      sublabel: `${displayTarget} (${recordCount} items)`,
      icon: Globe,
      state: 'active',
      badge: `${recordCount} Items`,
    },
    {
      id: 'scraping',
      label: 'SCRAPING',
      sublabel: isFailed ? 'Selectors Broken' : isHealing ? 'Re-extracting...' : 'Bright Data / Mock Client',
      icon: Cpu,
      state: isFailed ? 'failed' : isHealing ? 'healing' : 'active',
      badge: isFailed ? 'Failed' : isHealing ? 'Adapting' : 'Executing',
    },
    {
      id: 'data',
      label: 'EXTRACTED DATA',
      sublabel: isFailed ? '0 records (Missing fields)' : `${recordCount} records normalized`,
      icon: Database,
      state: isFailed ? 'failed' : 'active',
      badge: isFailed ? '0 Items' : `${recordCount} Items`,
    },
    {
      id: 'validation',
      label: 'VALIDATION',
      sublabel: isFailed ? 'Schema check failed' : 'Pydantic v2 verified',
      icon: ShieldCheck,
      state: isFailed ? 'failed' : 'active',
      badge: isFailed ? 'Invalid' : '100% Valid',
    },
    {
      id: 'health',
      label: 'HEALTH STATUS',
      sublabel: isHealthy ? 'Healthy & verified' : isFailed ? 'Action required' : 'Self-healing...',
      icon: HeartPulse,
      state: isFailed ? 'failed' : isHealing ? 'healing' : 'active',
      badge: isHealthy ? 'HEALTHY' : isFailed ? 'DEGRADED' : 'HEALING',
    },
  ];

  return (
    <div className="pipeline-flow-container glass-panel">
      <div className="pipeline-flow-header">
        <span className="pipeline-title">END-TO-END DATA PIPELINE ARCHITECTURE</span>
        <span className="pipeline-role-tag">ScrapeGuard Self-Healing Orchestration Layer</span>
      </div>
      <div className="pipeline-steps-row">
        {steps.map((step, idx) => {
          const Icon = step.icon;
          return (
            <React.Fragment key={step.id}>
              <div className={`pipeline-step-node node-${step.state}`}>
                <div className="node-icon-box">
                  <Icon size={16} />
                </div>
                <div className="node-text-col">
                  <div className="node-label-row">
                    <span className="node-label">{step.label}</span>
                    <span className={`node-badge badge-${step.state}`}>{step.badge}</span>
                  </div>
                  <span className="node-sublabel">{step.sublabel}</span>
                </div>
              </div>
              {idx < steps.length - 1 && (
                <div className={`pipeline-arrow arrow-${step.state}`}>
                  <ArrowRight size={16} />
                </div>
              )}
            </React.Fragment>
          );
        })}
      </div>
    </div>
  );
}
