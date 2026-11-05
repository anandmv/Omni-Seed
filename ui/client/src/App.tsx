import './App.css';
import { useDashboard } from './hooks/useDashboard';
import { StatsBar } from './components/StatsBar';
import { ActiveJobs } from './components/ActiveJobs';
import { MockPanel } from './components/MockPanel';
import { ExportPanel } from './components/ExportPanel';
import { JobsTable } from './components/JobsTable';

function App() {
  const { data, loading, error, lastUpdated, refresh } = useDashboard();

  const formattedTime = lastUpdated
    ? lastUpdated.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit', second: '2-digit' })
    : '—';

  return (
    <div className="app">
      <header className="app-header">
        <div className="app-header__brand">
          <span className="app-header__logo">🌱</span>
          <span className="app-header__title">OmniSeed</span>
          <span className="app-header__subtitle">Data Pipeline Dashboard</span>
        </div>
        <div className="app-header__controls">
          <span className="app-header__updated">Updated {formattedTime}</span>
          <button className="btn btn--icon" onClick={refresh} disabled={loading} title="Refresh now">
            <span className={loading ? 'spin' : ''}>🔄</span>
          </button>
          <span className="app-header__auto-badge">● Auto 5s</span>
        </div>
      </header>

      <main className="app-main">
        {error && (
          <div className="error-banner">
            <strong>⚠ API Error:</strong> {error}
          </div>
        )}

        {!data && loading && (
          <div className="loading-state">Loading dashboard…</div>
        )}

        {data && (
          <>
            <StatsBar
              stats={data.stats}
              totalResults={data.totalResults}
              avgDurationSeconds={data.avgDurationSeconds}
            />

            <ActiveJobs activeJobs={data.activeJobs} />

            <div className="panels-row">
              <MockPanel onRefresh={refresh} />
              <ExportPanel />
            </div>

            <JobsTable jobs={data.recentJobs} onRefresh={refresh} />
          </>
        )}
      </main>
    </div>
  );
}

export default App;
