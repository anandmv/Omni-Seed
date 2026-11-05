import { useState } from 'react';

interface MockPanelProps {
  onRefresh: () => void;
}

interface InjectResult {
  job_id?: string;
  message?: string;
}

export function MockPanel({ onRefresh }: MockPanelProps) {
  const [status, setStatus] = useState<string | null>(null);
  const [injecting, setInjecting] = useState<string | null>(null);

  const inject = async (type: 'sensor' | 'wearable') => {
    setInjecting(type);
    setStatus(null);
    try {
      const res = await fetch(`/api/mock/${type}`, { method: 'POST' });
      if (!res.ok) {
        throw new Error(`Server returned ${res.status}`);
      }
      const data: InjectResult = await res.json();
      const jobId = data.job_id ?? '(unknown)';
      setStatus(`✓ ${type === 'sensor' ? 'Sensor' : 'Wearable'} injected — job ${jobId.slice(0, 8)}`);
      onRefresh();
    } catch (err) {
      setStatus(`✗ Failed: ${err instanceof Error ? err.message : 'Unknown error'}`);
    } finally {
      setInjecting(null);
    }
  };

  return (
    <div className="panel">
      <h3 className="panel__title">Mock Data Injection</h3>
      <p className="panel__description">Inject synthetic sensor or wearable data into the queue.</p>
      <div className="panel__actions">
        <button
          className="btn btn--primary"
          onClick={() => inject('sensor')}
          disabled={injecting !== null}
        >
          {injecting === 'sensor' ? 'Injecting…' : '📡 Inject Sensor'}
        </button>
        <button
          className="btn btn--secondary"
          onClick={() => inject('wearable')}
          disabled={injecting !== null}
        >
          {injecting === 'wearable' ? 'Injecting…' : '⌚ Inject Wearable'}
        </button>
      </div>
      {status && (
        <p className={`panel__status ${status.startsWith('✓') ? 'panel__status--success' : 'panel__status--error'}`}>
          {status}
        </p>
      )}
    </div>
  );
}
