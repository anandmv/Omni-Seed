export type SourceType = 'iot' | 'wearable' | 'upload';
export type JobStatus = 'received' | 'processing' | 'summarized' | 'raw_deleted' | 'failed';

export interface Job {
  job_id: string;
  source_id: string;
  source_type: SourceType;
  status: JobStatus;
  received_at: string;
  completed_at: string | null;
  error_message: string | null;
  locked_by: string | null;
  summary: string | null;
  tags: string[];
  anomaly_flag: 0 | 1;
  measurements: Record<string, unknown>;
  system_fingerprint: string | null;
}

export interface ActiveJob {
  job_id: string;
  source_id: string;
  source_type: SourceType;
  locked_by: string;
  locked_at: string;
  locked_seconds: number;
}

export interface QueueStats {
  received: number;
  processing: number;
  summarized: number;
  failed: number;
  raw_deleted: number;
}

export interface DashboardData {
  stats: QueueStats;
  totalResults: number;
  avgDurationSeconds: number;
  activeJobs: ActiveJob[];
  recentJobs: Job[];
}
