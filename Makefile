COMPOSE := docker compose
SERVICES := neo4j faiss flask
PY_PATH := /app

.PHONY: help up build rebuild down restart logs ps migrate test shell wait-neo4j

help:
	@echo "Makefile targets:"
	@echo "  make up           # build & start services (neo4j, faiss, flask)"
	@echo "  make build        # build flask image"
	@echo "  make rebuild      # rebuild & start services"
	@echo "  make down         # stop and remove containers"
	@echo "  make restart      # restart services"
	@echo "  make logs         # show flask logs (tail 200)"
	@echo "  make ps           # show docker-compose ps"
	@echo "  make wait-neo4j   # wait until neo4j accepts cypher connections"
	@echo "  make migrate      # run neo4j migration inside flask container"
	@echo "  make test         # run async test inside flask container"
	@echo "  make shell        # open a shell in the flask container"

up: build
	$(COMPOSE) up -d $(SERVICES)

build:
	$(COMPOSE) build flask

rebuild:
	$(COMPOSE) up -d --build $(SERVICES)

down:
	$(COMPOSE) down

restart: down up

logs:
	$(COMPOSE) logs --no-color --tail 200 flask

ps:
	$(COMPOSE) ps

wait-neo4j:
	@echo "waiting for neo4j..."
	@i=0; while [ $$i -lt 60 ]; do \
	  if $(COMPOSE) exec -T neo4j cypher-shell -u neo4j -p "$${NEO4J_PASSWORD:-testpassword123}" "RETURN 1" >/dev/null 2>&1; then \
	    echo "neo4j ready"; exit 0; \
	  fi; \
	  i=$$((i+1)); echo "waiting... ($$i/60)"; sleep 2; \
	done; echo "neo4j did not become ready" >&2; exit 1

migrate: wait-neo4j
	$(COMPOSE) exec flask sh -c 'PYTHONPATH=$(PY_PATH) python agentic_engine/neo4j_migration.py migrate_audit'

migrate_audit: wait-neo4j
	$(COMPOSE) exec flask sh -c 'PYTHONPATH=$(PY_PATH) python agentic_engine/neo4j_migration.py migrate_audit'

seed_audit: wait-neo4j
	$(COMPOSE) exec flask sh -c 'PYTHONPATH=$(PY_PATH) python agentic_engine/neo4j_migration.py seed_audit'

ingest_demo: wait-neo4j
	$(COMPOSE) exec flask sh -c 'PYTHONPATH=$(PY_PATH) python -c "from agentic_engine.tools.document_ingest_tool import DocumentIngestTool; print(DocumentIngestTool().ingest_document(\"Q1_2024_Financials.pdf\"))"'


migrate: wait-neo4j
	$(COMPOSE) exec flask sh -c 'PYTHONPATH=$(PY_PATH) python agentic_engine/neo4j_migration.py migrate_audit'

migrate_audit: wait-neo4j
	$(COMPOSE) exec flask sh -c 'PYTHONPATH=$(PY_PATH) python agentic_engine/neo4j_migration.py migrate_audit'

seed_audit: wait-neo4j
	$(COMPOSE) exec flask sh -c 'PYTHONPATH=$(PY_PATH) python agentic_engine/neo4j_migration.py seed_audit'
