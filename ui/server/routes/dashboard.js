import { Router } from 'express';
import db from '../db.js';

const router = Router();

// Get queue status, active workers, metrics, and recent jobs
router.get('/queue/stats', (req, res) => {
  try {
    // 1. Get counts by status
    const statusRows = db
      .prepare('SELECT status, COUNT(*) as count FROM jobs GROUP BY status')
      .all();

    const stats = {
      received: 0,
      processing: 0,
      summarized: 0,
      failed: 0,
      raw_deleted: 0,
    };
    statusRows.forEach((row) => {
      if (row.status in stats) {
        stats[row.status] = row.count;
      }
    });

    // 2. Get total analysis results
    const resultsCountRow = db
      .prepare('SELECT COUNT(*) as count FROM analysis_results')
      .get();
    const totalResults = resultsCountRow ? resultsCountRow.count : 0;

    // 3. Get average execution duration (in seconds)
    // completed_at and received_at are ISO 8601 strings.
    const avgDurationRow = db
      .prepare(
        `SELECT AVG((julianday(completed_at) - julianday(received_at)) * 86400) as avg_seconds
         FROM jobs
         WHERE completed_at IS NOT NULL AND status IN ('summarized', 'raw_deleted')`
      )
      .get();
    const avgDurationSeconds = avgDurationRow && avgDurationRow.avg_seconds 
      ? Math.round(avgDurationRow.avg_seconds * 10) / 10 
      : 0;

    // 4. Get active locked jobs (in-flight)
    const activeJobs = db
      .prepare(
        `SELECT job_id, source_id, source_type, locked_by, locked_at,
                (julianday('now') - julianday(locked_at)) * 86400 as locked_seconds
         FROM jobs
         WHERE status = 'processing'`
      )
      .all()
      .map((row) => ({
        ...row,
        locked_seconds: row.locked_seconds ? Math.round(row.locked_seconds) : 0,
      }));

    // 5. Get recent 50 jobs
    const recentJobs = db
      .prepare(
        `SELECT job_id, source_id, source_type, status, received_at, completed_at, error_message, locked_by
         FROM jobs
         ORDER BY received_at DESC
         LIMIT 50`
      )
      .all();

    return res.json({
      stats,
      totalResults,
      avgDurationSeconds,
      activeJobs,
      recentJobs,
    });
  } catch (error) {
    console.error('Error fetching queue stats:', error);
    return res.status(500).json({ error: 'failed to fetch queue stats', details: error.message });
  }
});

// Retry a single failed job
router.post('/queue/retry/:job_id', (req, res) => {
  const { job_id } = req.params;
  try {
    const result = db
      .prepare(
        `UPDATE jobs
         SET status = 'received', completed_at = NULL, locked_by = NULL, locked_at = NULL, error_message = NULL
         WHERE job_id = ? AND status = 'failed'`
      )
      .run(job_id);

    if (result.changes === 0) {
      return res.status(404).json({ error: 'failed job not found or not in failed status' });
    }

    return res.json({ success: true, message: `Job ${job_id} enqueued for retry` });
  } catch (error) {
    console.error('Error retrying job:', error);
    return res.status(500).json({ error: 'failed to retry job', details: error.message });
  }
});

// Retry all failed jobs
router.post('/queue/retry-all', (req, res) => {
  try {
    const result = db
      .prepare(
        `UPDATE jobs
         SET status = 'received', completed_at = NULL, locked_by = NULL, locked_at = NULL, error_message = NULL
         WHERE status = 'failed'`
      )
      .run();

    return res.json({ success: true, changes: result.changes, message: `${result.changes} jobs enqueued for retry` });
  } catch (error) {
    console.error('Error retrying all jobs:', error);
    return res.status(500).json({ error: 'failed to retry all jobs', details: error.message });
  }
});

// Proxy route to trigger mock sensor ingestion on collector API
router.post('/mock/sensor', async (req, res) => {
  try {
    const response = await fetch('http://127.0.0.1:8000/ingest/sensor', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        device_id: `sensor-mock-${Math.floor(100 + Math.random() * 900)}`,
        payload: {
          temperature: parseFloat((18 + Math.random() * 18).toFixed(1)),
          humidity: Math.floor(35 + Math.random() * 50),
          battery: Math.floor(50 + Math.random() * 50),
          timestamp: new Date().toISOString(),
        },
      }),
    });
    const data = await response.json();
    return res.json(data);
  } catch (error) {
    return res.status(500).json({ error: 'failed to trigger mock sensor ingestion', details: error.message });
  }
});

// Proxy route to trigger mock wearable ingestion on collector API
router.post('/mock/wearable', async (req, res) => {
  try {
    const response = await fetch('http://127.0.0.1:8000/ingest/wearable-event', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        device_id: `wearable-mock-${Math.floor(100 + Math.random() * 900)}`,
        payload: {
          steps: Math.floor(1000 + Math.random() * 12000),
          heart_rate: Math.floor(55 + Math.random() * 80),
          sleep_hours: parseFloat((4 + Math.random() * 5).toFixed(1)),
          activity_type: ['walk', 'run', 'cycle', 'sleep'][Math.floor(Math.random() * 4)],
        },
      }),
    });
    const data = await response.json();
    return res.json(data);
  } catch (error) {
    return res.status(500).json({ error: 'failed to trigger mock wearable ingestion', details: error.message });
  }
});

export default router;
