#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PID_FILE="$ROOT/.run-locally.pids"
DB_FILE="$ROOT/omniseed.db"
SCHEMA_FILE="$ROOT/db/schema.sql"
UI_SERVER_DIR="$ROOT/ui/server"
UI_SERVER_FILE="$UI_SERVER_DIR/server.js"

usage() {
  cat <<EOF
Usage: $0 <command>

Commands:
  init      Create the SQLite DB, install Python and Node deps
  start     Start collector API, poller, analyser worker, and UI server
  stop      Stop processes started by this script
  help      Show this help message

Examples:
  $0 init
  $0 start
  $0 stop
EOF
}

ensure_command() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "ERROR: '$1' is required but not installed."
    exit 1
  fi
}

init() {
  ensure_command uv
  ensure_command sqlite3
  ensure_command yarn

  cd "$ROOT"

  if [ ! -f "$DB_FILE" ]; then
    echo "Creating SQLite database $DB_FILE..."
    sqlite3 "$DB_FILE" < "$SCHEMA_FILE"
  else
    echo "$DB_FILE already exists; skipping create."
  fi

  echo "Installing Python dependencies with uv..."
  uv sync

  echo "Installing Node dependencies for UI server..."
  cd "$UI_SERVER_DIR"
  yarn install

  echo "Initialization complete."
}

start() {
  ensure_command uv

  if [ -f "$PID_FILE" ]; then
    echo "ERROR: PID file exists at $PID_FILE. Is the stack already running?"
    exit 1
  fi

  cd "$ROOT"
  > "$PID_FILE"

  echo "Starting collector API on http://localhost:8000..."
  uv run uvicorn collector.main:app --reload --port 8000 &
  echo "$!" >> "$PID_FILE"

  echo "Starting collector poller..."
  uv run python collector/poller.py &
  echo "$!" >> "$PID_FILE"

  echo "Starting analyser worker..."
  uv run python analyser/worker.py &
  echo "$!" >> "$PID_FILE"

  if [ -f "$UI_SERVER_FILE" ]; then
    echo "Starting UI server..."
    cd "$UI_SERVER_DIR"
    node server.js &
    echo "$!" >> "$PID_FILE"
    cd "$ROOT"
  else
    echo "UI server entrypoint not found at $UI_SERVER_FILE; skipping UI startup."
  fi

  echo "Services started. PIDs written to $PID_FILE."
  echo "Use '$0 stop' to terminate them."
  wait
}

stop() {
  if [ ! -f "$PID_FILE" ]; then
    echo "No PID file found at $PID_FILE. Nothing to stop."
    exit 0
  fi

  echo "Stopping processes from $PID_FILE..."
  while read -r pid; do
    if [ -n "$pid" ] && kill -0 "$pid" >/dev/null 2>&1; then
      kill "$pid" || true
    fi
  done < "$PID_FILE"

  rm -f "$PID_FILE"
  echo "Stopped all managed processes."
}

case "${1:-help}" in
  init)
    init
    ;;
  start)
    start
    ;;
  stop)
    stop
    ;;
  help|--help|-h)
    usage
    ;;
  *)
    echo "Unknown command: ${1:-}" >&2
    usage
    exit 1
    ;;
 esac
