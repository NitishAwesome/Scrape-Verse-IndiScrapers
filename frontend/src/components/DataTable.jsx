import React from 'react';
import { Database, CheckCircle2, XCircle, AlertCircle, ShoppingBag } from 'lucide-react';

export default function DataTable({ records = [], status, error, lastUpdated }) {
  const isFailed = status === 'failed' || status === 'FAILED';

  return (
    <div className="glass-panel data-table-panel">
      <div className="panel-header-row">
        <div className="panel-title-group">
          <Database className="text-cyan" size={18} />
          <h4 className="panel-title">Extracted Product Data</h4>
          <span className="badge badge-cyan">{records.length} Record{records.length === 1 ? '' : 's'}</span>
        </div>
        <div className="mono-font text-muted text-xs">
          Updated: {lastUpdated || 'Never'}
        </div>
      </div>

      <div className="table-responsive">
        <table className="custom-data-table">
          <thead>
            <tr>
              <th>Product Title</th>
              <th>Price</th>
              <th>Stock Status</th>
              <th>Data Pipeline State</th>
            </tr>
          </thead>
          <tbody>
            {isFailed ? (
              <tr className="table-row-error">
                <td colSpan="4" className="error-empty-cell">
                  <div className="empty-state-box">
                    <XCircle className="text-red" size={32} />
                    <div>
                      <div className="text-red font-semibold">Extraction Blocked — Selector Failure</div>
                      <div className="text-muted text-sm mono-font">
                        {error || 'SelectorNotFound: .product-price • Required field missing'}
                      </div>
                    </div>
                  </div>
                </td>
              </tr>
            ) : records.length > 0 ? (
              records.map((item, index) => (
                <tr key={index} className="table-row-item animate-fade-in">
                  <td className="font-medium text-light">
                    <div className="product-cell">
                      <ShoppingBag size={16} className="text-cyan" />
                      <span>{item.title}</span>
                    </div>
                  </td>
                  <td className="mono-font text-emerald font-semibold text-base">
                    {item.price}
                  </td>
                  <td>
                    <span className="badge badge-emerald">
                      <CheckCircle2 size={12} /> {item.stock_status || item.status}
                    </span>
                  </td>
                  <td>
                    <div className="pipeline-status-badge">
                      <span className="status-dot status-dot-emerald"></span>
                      <span className="text-xs text-secondary mono-font">Normalized & Validated</span>
                    </div>
                  </td>
                </tr>
              ))
            ) : (
              <tr>
                <td colSpan="4" className="text-center text-muted py-8">
                  <AlertCircle size={24} className="mx-auto mb-2 text-muted" />
                  No extracted records available. Click "Run Scraper" to fetch data.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
