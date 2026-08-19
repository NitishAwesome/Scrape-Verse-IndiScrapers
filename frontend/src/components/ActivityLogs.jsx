import React, { useState } from 'react';
import { Terminal, Trash2, Eye, X, Check, Copy } from 'lucide-react';

export default function ActivityLogs({ logs = [], onClear, rawPayload }) {
  const [showJsonModal, setShowJsonModal] = useState(false);
  const [copied, setCopied] = useState(false);

  const copyJson = () => {
    navigator.clipboard.writeText(JSON.stringify(rawPayload, null, 2));
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const getLevelBadge = (level) => {
    switch (level) {
      case 'HEAL':
        return <span className="log-badge log-badge-violet">HEAL</span>;
      case 'WARN':
        return <span className="log-badge log-badge-amber">WARN</span>;
      case 'ERROR':
        return <span className="log-badge log-badge-red">ERR</span>;
      default:
        return <span className="log-badge log-badge-cyan">INFO</span>;
    }
  };

  return (
    <div className="glass-panel logs-panel">
      <div className="panel-header-row">
        <div className="panel-title-group">
          <Terminal className="text-emerald" size={18} />
          <h4 className="panel-title">Real-Time Diagnostic Stream</h4>
          <span className="badge badge-emerald">{logs.length} Events</span>
        </div>

        <div className="log-actions">
          {rawPayload && (
            <button
              className="btn btn-secondary btn-sm"
              onClick={() => setShowJsonModal(true)}
            >
              <Eye size={13} />
              <span>Inspect JSON</span>
            </button>
          )}

          <button
            className="btn btn-secondary btn-sm"
            onClick={onClear}
            title="Clear Stream"
          >
            <Trash2 size={13} />
            <span>Clear</span>
          </button>
        </div>
      </div>

      <div className="log-stream-box mono-font">
        {logs.length > 0 ? (
          logs.map((item, index) => (
            <div key={index} className="log-entry-row animate-fade-in">
              <span className="log-time text-muted">{item.time}</span>
              {getLevelBadge(item.level)}
              <span className={`log-msg ${item.level === 'ERROR' ? 'text-red' : item.level === 'HEAL' ? 'text-emerald font-semibold' : 'text-secondary'}`}>
                {item.message}
              </span>
            </div>
          ))
        ) : (
          <div className="text-muted text-center py-6 text-xs">
            Diagnostic event stream listening... Trigger actions above to stream telemetry.
          </div>
        )}
      </div>

      {showJsonModal && (
        <div className="modal-backdrop" onClick={() => setShowJsonModal(false)}>
          <div className="modal-card glass-panel" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <div className="modal-title-group">
                <Terminal size={18} className="text-cyan" />
                <h4 className="text-light font-semibold">Raw Engine JSON Payload</h4>
              </div>
              <div className="flex-center gap-2">
                <button className="btn btn-secondary btn-sm" onClick={copyJson}>
                  {copied ? <Check size={14} className="text-emerald" /> : <Copy size={14} />}
                  <span>{copied ? 'Copied' : 'Copy JSON'}</span>
                </button>
                <button className="btn btn-secondary btn-icon btn-sm" onClick={() => setShowJsonModal(false)}>
                  <X size={16} />
                </button>
              </div>
            </div>
            <div className="modal-body">
              <pre className="json-pre mono-font">{JSON.stringify(rawPayload, null, 2)}</pre>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
