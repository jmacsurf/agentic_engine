# Agentic Choreography Engine

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

