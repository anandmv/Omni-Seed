import type { ActiveJob } from '../types';

interface ActiveJobsProps {
  activeJobs: ActiveJob[];
}

export function ActiveJobs({ activeJobs }: ActiveJobsProps) {
  if (activeJobs.length === 0) return null;

  return (
    <section className="active-jobs">
      <div className="active-jobs__header">
        <span className="active-jobs__icon">⚡</span>
        <strong>{activeJobs.length} job{activeJobs.length !== 1 ? 's' : ''} in-flight</strong>
      </div>
      <div className="table-wrapper">
        <table className="table">
          <thead>
            <tr>
              <th>Job ID</th>
              <th>Source ID</th>
              <th>Type</th>
              <th>Locked By</th>
              <th>Running For</th>
            </tr>
          </thead>
          <tbody>
            {activeJobs.map((job) => (
              <tr key={job.job_id}>
                <td>
                  <code className="monospace">{job.job_id.slice(0, 8)}</code>
                </td>
                <td>{job.source_id}</td>
                <td>
                  <span className={`badge badge--${job.source_type}`}>{job.source_type}</span>
                </td>
                <td>{job.locked_by}</td>
                <td>{job.locked_seconds}s</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
