#!/usr/bin/env bash
set -euo pipefail

SERVICE="flask"

usage() {
  cat <<'USAGE'
Usage:
  run_in_container.sh [service] -- <command...>
Examples:
  run_in_container.sh flask -- python /app/tests/test_async_run.py
  run_in_container.sh -- python /app/neo4j_migration.py migrate_audit
USAGE
  exit 1
}

if [ $# -eq 0 ]; then
  usage
fi

if [ "$1" = "--" ]; then
  shift
elif [ $# -ge 2 ] && [ "$2" = "--" ]; then
  SERVICE="$1"
  shift 2
fi

[ $# -eq 0 ] && usage

CMD="$*"

docker compose exec -T "$SERVICE" sh -c "PYTHONPATH=/app $CMD"
