# OmniSeed Local Test Plan

This document describes a local testing workflow for OmniSeed using sample data.
It follows the same path as the normal workflow: ingest → analyse → persist → export.

## 1. Start the stack

From the repository root:

```bash
./run-locally.sh init
./run-locally.sh start
```

If the UI server does not start automatically, run:

```bash
cd ui/server
npm start
```

## 2. Confirm the collector API is available

The collector should listen on `http://localhost:8000`.

```bash
curl http://localhost:8000/docs
```

## 3. Submit sample ingestion data

### 3.1 IoT sensor payload

```bash
curl -X POST http://localhost:8000/ingest/sensor \
  -H "Content-Type: application/json" \
  -d '{
    "device_id": "sensor-001",
    "payload": {
      "temperature": 32.8,
      "humidity": 78,
      "battery": 87,
      "timestamp": "2026-07-14T12:00:00Z"
    }
  }'
```

### 3.2 Wearable event payload

```bash
curl -X POST http://localhost:8000/ingest/wearable-event \
  -H "Content-Type: application/json" \
  -d '{
    "device_id": "wearable-123",
    "payload": {
      "steps": 12400,
      "heart_rate": 113,
      "sleep_hours": 6.1,
      "activity_type": "walk"
    }
  }'
```

### 3.3 Upload file payload

Create a sample file first:

```bash
printf 'Daily maintenance report: no incidents. All sensor readings nominal.' > /tmp/omniseed-sample.txt
```

Then submit it:

```bash
curl -X POST http://localhost:8000/ingest/upload \
  -F "file=@/tmp/omniseed-sample.txt"
```

## 4. Wait for analysis

The analyser worker will poll for received jobs and process them.
Allow a few seconds for the analysis to complete.

## 5. Validate persisted results

### 5.1 Query SQLite directly

```bash
sqlite3 omniseed.db "SELECT job_id, source_type, summary, anomaly_flag, created_at FROM analysis_results ORDER BY created_at DESC;"
```

If the table is empty, review `omniseed.db` and the worker logs for errors.

### 5.2 Check job lifecycle

```bash
sqlite3 omniseed.db "SELECT job_id, status, completed_at, error_message FROM jobs ORDER BY received_at DESC;"
```

Expected statuses:
- `raw_deleted` for successfully completed jobs
- `failed` if the worker encountered an error

## 6. Export the results from the UI server

The UI server exposes export routes under `/api/export`.

### JSON export

```bash
curl http://localhost:3000/api/export/json | jq .
```

### CSV export

```bash
curl http://localhost:3000/api/export/csv -o omniseed-export.csv
```

### PDF export

```bash
curl http://localhost:3000/api/export/pdf -o omniseed-export.pdf
```

## 7. Clean up

Stop the services when done:

```bash
./run-locally.sh stop
```

## 8. Notes

- The collector uses `OMNISEED_DB_PATH` if set to point at a different SQLite file.
- If LM Studio is not running locally on `localhost:1234`, the analyser worker will fail.
- The upload endpoint stores temp files under `/tmp/omniseed/{job_id}` and removes them after successful analysis.
