import { useState } from 'react';

type SourceFilter = '' | 'iot' | 'wearable' | 'upload';

function buildQuery(source: SourceFilter, from: string, to: string): string {
  const params = new URLSearchParams();
  if (source) params.set('source_type', source);
  if (from) params.set('from', from);
  if (to) params.set('to', to);
  const qs = params.toString();
  return qs ? `?${qs}` : '';
}

export function ExportPanel() {
  const [source, setSource] = useState<SourceFilter>('');
  const [from, setFrom] = useState<string>('');
  const [to, setTo] = useState<string>('');

  const exportData = (format: 'json' | 'csv' | 'pdf') => {
    const qs = buildQuery(source, from, to);
    const url = `/api/export/${format}${qs}`;
    if (format === 'json') {
      window.open(url, '_blank');
    } else {
      window.location.href = url;
    }
  };

  return (
    <div className="panel">
      <h3 className="panel__title">Export Data</h3>
      <p className="panel__description">Download processed job results with optional filters.</p>
      <div className="export-filters">
        <label className="form-label">
          Source Type
          <select
            className="form-select"
            value={source}
            onChange={(e) => setSource(e.target.value as SourceFilter)}
          >
            <option value="">All</option>
            <option value="iot">IoT</option>
            <option value="wearable">Wearable</option>
            <option value="upload">Upload</option>
          </select>
        </label>
        <label className="form-label">
          From
          <input
            type="datetime-local"
            className="form-input"
            value={from}
            onChange={(e) => setFrom(e.target.value)}
          />
        </label>
        <label className="form-label">
          To
          <input
            type="datetime-local"
            className="form-input"
            value={to}
            onChange={(e) => setTo(e.target.value)}
          />
        </label>
      </div>
      <div className="panel__actions">
        <button className="btn btn--outline" onClick={() => exportData('json')}>
          📄 JSON
        </button>
        <button className="btn btn--outline" onClick={() => exportData('csv')}>
          📊 CSV
        </button>
        <button className="btn btn--outline" onClick={() => exportData('pdf')}>
          📑 PDF
        </button>
      </div>
    </div>
  );
}
