import { useState, useMemo } from 'react';
import type { Job, JobStatus, SourceType } from '../types';

interface JobsTableProps {
  jobs: Job[];
  onRefresh: () => void;
}

type StatusFilter = '' | JobStatus;
type SourceFilter = '' | SourceType;

const STATUS_LABELS: Record<JobStatus, string> = {
  received: 'Received',
  processing: 'Processing',
  summarized: 'Summarized',
  raw_deleted: 'Raw Deleted',
  failed: 'Failed',
};

function StatusBadge({ status }: { status: JobStatus }) {
  return <span className={`badge badge--status badge--${status}`}>{STATUS_LABELS[status]}</span>;
}

function formatTime(iso: string | null): string {
  if (!iso) return '—';
  const d = new Date(iso);
  return d.toLocaleString(undefined, {
    month: 'short',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  });
}

export function JobsTable({ jobs, onRefresh }: JobsTableProps) {
  const [statusFilter, setStatusFilter] = useState<StatusFilter>('');
  const [sourceFilter, setSourceFilter] = useState<SourceFilter>('');
  const [searchText, setSearchText] = useState<string>('');
  const [retrying, setRetrying] = useState<string | null>(null);
  const [retryingAll, setRetryingAll] = useState<boolean>(false);

  const failedJobs = useMemo(() => jobs.filter((j) => j.status === 'failed'), [jobs]);

  const filteredJobs = useMemo(() => {
    return jobs.filter((job) => {
      if (statusFilter && job.status !== statusFilter) return false;
      if (sourceFilter && job.source_type !== sourceFilter) return false;
      if (searchText) {
        const q = searchText.toLowerCase();
        const matchesId = job.source_id.toLowerCase().includes(q);
        const matchesSummary = job.summary?.toLowerCase().includes(q) ?? false;
        if (!matchesId && !matchesSummary) return false;
      }
      return true;
    });
  }, [jobs, statusFilter, sourceFilter, searchText]);

  const handleRetry = async (jobId: string) => {
    setRetrying(jobId);
    try {
      await fetch(`/api/queue/retry/${jobId}`, { method: 'POST' });
      onRefresh();
    } finally {
      setRetrying(null);
    }
  };

  const handleRetryAll = async () => {
    setRetryingAll(true);
    try {
      await fetch('/api/queue/retry-all', { method: 'POST' });
      onRefresh();
    } finally {
      setRetryingAll(false);
    }
  };

  return (
    <section className="jobs-section">
      <div className="jobs-header">
        <h3 className="jobs-header__title">Recent Jobs</h3>
        {failedJobs.length > 0 && (
          <button
            className="btn btn--danger"
            onClick={handleRetryAll}
            disabled={retryingAll}
          >
            {retryingAll ? 'Retrying…' : `↺ Retry All Failed (${failedJobs.length})`}
          </button>
        )}
      </div>

      <div className="filter-bar">
        <input
          type="text"
          className="form-input filter-bar__search"
          placeholder="Search source ID or summary…"
          value={searchText}
          onChange={(e) => setSearchText(e.target.value)}
        />
        <select
          className="form-select"
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value as StatusFilter)}
        >
          <option value="">All Statuses</option>
          <option value="received">Received</option>
          <option value="processing">Processing</option>
          <option value="summarized">Summarized</option>
          <option value="raw_deleted">Raw Deleted</option>
          <option value="failed">Failed</option>
        </select>
        <select
          className="form-select"
          value={sourceFilter}
          onChange={(e) => setSourceFilter(e.target.value as SourceFilter)}
        >
          <option value="">All Types</option>
          <option value="iot">IoT</option>
          <option value="wearable">Wearable</option>
          <option value="upload">Upload</option>
        </select>
      </div>

      <div className="table-wrapper">
        {filteredJobs.length === 0 ? (
          <p className="empty-state">No jobs match the current filters.</p>
        ) : (
          <table className="table">
            <thead>
              <tr>
                <th>Time</th>
                <th>Source ID</th>
                <th>Type</th>
                <th>Status</th>
                <th>Summary</th>
                <th>Anomaly</th>
                <th>Tags</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {filteredJobs.map((job) => (
                <tr key={job.job_id} className={job.anomaly_flag ? 'row--anomaly' : ''}>
                  <td className="cell--time">{formatTime(job.received_at)}</td>
                  <td>
                    <code className="monospace">{job.source_id}</code>
                  </td>
                  <td>
                    <span className={`badge badge--${job.source_type}`}>{job.source_type}</span>
                  </td>
                  <td>
                    <StatusBadge status={job.status} />
                  </td>
                  <td className="cell--summary">
                    {job.summary ? (
                      <span title={job.summary}>{job.summary.slice(0, 60)}{job.summary.length > 60 ? '…' : ''}</span>
                    ) : (
                      <span className="text-muted">—</span>
                    )}
                  </td>
                  <td className="cell--anomaly">
                    {job.anomaly_flag === 1 && (
                      <span className="anomaly-flag" title="Anomaly detected">⚠</span>
                    )}
                  </td>
                  <td className="cell--tags">
                    {job.tags && job.tags.length > 0 ? (
                      <div className="tags">
                        {job.tags.map((tag) => (
                          <span key={tag} className="tag">{tag}</span>
                        ))}
                      </div>
                    ) : (
                      <span className="text-muted">—</span>
                    )}
                  </td>
                  <td>
                    {job.status === 'failed' && (
                      <button
                        className="btn btn--sm btn--danger"
                        onClick={() => handleRetry(job.job_id)}
                        disabled={retrying === job.job_id}
                        title={job.error_message ?? undefined}
                      >
                        {retrying === job.job_id ? '…' : '↺ Retry'}
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </section>
  );
}
