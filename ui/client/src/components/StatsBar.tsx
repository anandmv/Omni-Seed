import type { QueueStats } from '../types';

interface StatsBarProps {
  stats: QueueStats;
  totalResults: number;
  avgDurationSeconds: number;
}

interface StatCardProps {
  label: string;
  value: number;
  colorClass: string;
}

function StatCard({ label, value, colorClass }: StatCardProps) {
  return (
    <div className={`stat-card stat-card--${colorClass}`}>
      <span className="stat-card__value">{value.toLocaleString()}</span>
      <span className="stat-card__label">{label}</span>
    </div>
  );
}

export function StatsBar({ stats, totalResults, avgDurationSeconds }: StatsBarProps) {
  return (
    <section className="stats-section">
      <div className="stats-grid">
        <StatCard label="Received" value={stats.received} colorClass="gray" />
        <StatCard label="Processing" value={stats.processing} colorClass="blue" />
        <StatCard label="Summarized" value={stats.summarized} colorClass="green" />
        <StatCard label="Failed" value={stats.failed} colorClass="red" />
        <StatCard label="Raw Deleted" value={stats.raw_deleted} colorClass="teal" />
      </div>
      <div className="stats-meta">
        <span className="stats-meta__item">
          <span className="stats-meta__label">Total Results</span>
          <span className="stats-meta__value">{totalResults.toLocaleString()}</span>
        </span>
        <span className="stats-meta__divider" />
        <span className="stats-meta__item">
          <span className="stats-meta__label">Avg Duration</span>
          <span className="stats-meta__value">
            {avgDurationSeconds != null ? `${avgDurationSeconds.toFixed(2)}s` : '—'}
          </span>
        </span>
      </div>
    </section>
  );
}
