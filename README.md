#!/usr/bin/env bash
# Simple helper to run commands inside the flask container with PYTHONPATH set.
set -euo pipefail

SERVICE="${1:-flask}"
shift || true

if [ $# -eq 0 ]; then
  echo "Usage: $0 [service] -- <command...>"
  echo "Example: $0 flask -- python /app/tests/test_async_run.py"
  exit 1
fi

# If invoked with leading --, adjust
if [ "$SERVICE" = "--" ]; then
  SERVICE="flask"
fi

# if first arg is a service and next arg is --, consume it
if [ "$1" = "--" ]; then
  shift
fi

CMD="$*"
if [ -z "$CMD" ]; then
  echo "No command provided"
  exit 1
fi

# Run the command inside the container with PYTHONPATH=/app
docker compose exec -T "$SERVICE" sh -c "PYTHONPATH=/app $CMD"#!/usr/bin/env bash
set -euo pipefail

SERVICE="${1:-flask}"
shift || true

if [ $# -eq 0 ]; then
  echo "Usage: $0 [service] -- <command...>"
  echo "Example: $0 flask -- python /app/tests/test_async_run.py"
  exit 1
fi

# if first arg is '--' (no service provided)
if [ "$SERVICE" = "--" ]; then
  SERVICE="flask"
else
  if [ "${1:-}" = "--" ]; then
    shift
  fi
fi

CMD="$*"
if [ -z "$CMD" ]; then
  echo "No command provided"
  exit 1
fi

docker compose exec -T "$SERVICE" sh -c "PYTHONPATH=/app $CMD"#!/usr/bin/env bash
set -euo pipefail

SERVICE="${1:-flask}"
shift || true

if [ $# -eq 0 ]; then
  echo "Usage: $0 [service] -- <command...>"
  echo "Example: $0 flask -- python /app/tests/test_async_run.py"
  exit 1
fi

# if first arg is '--' (no service provided)
if [ "$SERVICE" = "--" ]; then
  SERVICE="flask"
else
  if [ "${1:-}" = "--" ]; then
    shift
  fi
fi

CMD="$*"
if [ -z "$CMD" ]; then
  echo "No command provided"
  exit 1
fi

docker compose exec -T "$SERVICE" sh -c "PYTHONPATH=/app $CMD"mkdir -p scripts
cat > scripts/run_in_container.sh <<'SH'
#!/usr/bin/env bash
set -euo pipefail

SERVICE="${1:-flask}"
shift || true

if [ $# -eq 0 ]; then
  echo "Usage: $0 [service] -- <command...>"
  echo "Example: $0 flask -- python /app/tests/test_async_run.py"
  exit 1
fi

if [ "$SERVICE" = "--" ]; then
  SERVICE="flask"
else
  if [ "${1:-}" = "--" ]; then
    shift
  fi
fi

CMD="$*"
if [ -z "$CMD" ]; then
  echo "No command provided"
  exit 1
fi

docker compose exec -T "$SERVICE" sh -c "PYTHONPATH=/app $CMD"
SH

cat > README.md <<'MD'
# Agentic Choreography Engine

Run everything inside Docker to avoid macOS prompts and ensure a consistent environment.

Quick steps:
1. Build & start services:
   make rebuild

2. Wait for Neo4j:
   make wait-neo4j

3. Run DB migration:
   make migrate

4. Run tests / scripts inside the flask container:
   make test
   or:
   ./scripts/run_in_container.sh flask -- python /app/tests/test_async_run.py

Do NOT execute README.md as a script.
MD

chmod +x scripts/run_in_container.sh# Agentic Choreography Engine

Self-learning, governable, and auditable agent orchestration system.

Includes:
- LangGraph agent workflows
- Neo4j Knowledge Graph persistence
- FAISS semantic fallback
- Flask governance dashboard
- Docker Compose + Helm deployment
- Prometheus + Grafana monitoring
- Alertmanager for alerts
# agentic_engine

## Neo4j configuration and environment variables

The project reads Neo4j connection information from environment variables with sensible defaults:

- `NEO4J_URI` (default: `bolt://localhost:7687`)
- `NEO4J_USER` (default: `neo4j`)
- `NEO4J_PASSWORD` (default: `test`)

Set these before running the dashboard or connector to point to your Neo4j instance.

Example:

```bash
export NEO4J_URI=bolt://db.example.com:7687
export NEO4J_USER=neo4j
export NEO4J_PASSWORD=supersecret
python3 web_dashboard.py
```

## Integration tests (Docker)

There is an integration test that spins up a temporary Neo4j container and validates the `Neo4jConnector` against it. It's intentionally opt-in.

To run it locally:

1. Ensure Docker is installed and running on your machine.
2. Enable integration tests and run pytest:

```bash
export RUN_INTEGRATION_TESTS=1
PYTHONPATH=. pytest tests/test_neo4j_integration.py -q
```

The test will pull a Neo4j image (`neo4j:5.13`) and start a container with credentials `neo4j/test`. The container is stopped automatically after the test.


# 🤖 Agentic Engine

The **Agentic Engine** is a next-generation orchestration platform for **digital employees**.  
It supervises **multiple AI agents and tools** (API + RPA) using a **knowledge graph (Neo4j)**,  
with **governance, monitoring, and self-learning workflows**.

---

## 🚀 Executive Summary

The Agentic Engine:
- Mimics **human workflows** across applications, APIs, and UIs.
- Connects multiple tools (API, RPA, Slack, DB, etc.) into a **choreographed workflow**.
- Learns over time:
  - Successful paths are reinforced.
  - Failing or unused paths decay automatically.
  - Semantic fallback (via FAISS vectors) discovers new pathways.
- Provides **real-time governance**:
  - Human-in-the-loop dashboard for reviewing or approving AI decisions.
  - **RBAC controls**: Admins approve, viewers observe.
  - Policies auto-approve low-risk tasks, escalate high-risk tasks.
- Monitors operations:
  - Integrated **Prometheus + Grafana** dashboards.
  - Alerts for failure spikes, KG growth, or scaling events.

**Think of it as your digital workforce supervisor**:  
reliably delegating, monitoring, and adapting agents to complete real-world business tasks.

---

## 🛠 Developer Setup

### 1. Clone the Repository

```bash
git clone https://github.com/jmacsurf/agentic_engine.git
cd agentic_engine

