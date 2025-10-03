from __future__ import annotations
import os
import logging
import yaml
import json
import uuid
from neo4j import GraphDatabase
from datetime import datetime

# Configure Python logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

logger = logging.getLogger(__name__)

class Neo4jConnector:
    
    def __init__(
        self,
        uri: str | None = None,
        user: str | None = None,
        password: str | None = None,
        policy_file="config/severity_policy.yaml"
    ):
        """
        Neo4jConnector is the bridge between the Agentic Engine and Neo4j.
        Handles workflows, execution traces, decisions, and feedback loops.
        """
        # initialize connection parameters from args or env
        self.uri = uri or os.getenv("NEO4J_URI", "bolt://neo4j:7687")
        self.user = user or os.getenv("NEO4J_USER", "neo4j")
        self.password = password or os.getenv("NEO4J_PASSWORD", "testpassword123")
        self.policy_file = policy_file
        self.driver = None
        self._available = False

        try:
            self.driver = GraphDatabase.driver(self.uri, auth=(self.user, self.password))
            self._available = True
            # Try to call a license procedure if present, but ignore if not available (Community / older servers)
            try:
                with self.driver.session() as session:
                    session.run("CALL dbms.licenseAgreementDetails()").consume()
            except Exception as e:
                logging.info("dbms.licenseAgreementDetails not available or failed: %s -- continuing without license check", e)
        except Exception as e:
            logging.error("Failed to create Neo4j driver: %s", e)
            self.driver = None
            self._available = False

        # Load policy file (does not rely on DB availability)
        self.reload_policy()

    def close(self):
        """Gracefully close the Neo4j connection."""
        try:
            if getattr(self, "driver", None) is not None:
                self.driver.close()
        except Exception:
            logging.warning("Failed to close Neo4j driver cleanly.")

    # =====================================================
    # === EVENT LOGGING ===================================
    # =====================================================
    def log_event(self, event_type, message, metadata=None):
        """
        Log events to both Python logger and Neo4j as Event nodes.
        :param event_type: string ("decision", "trace", "feedback", etc.)
        :param message: human-readable message
        :param metadata: dict (extra details)
        """
        logging.info(f"[{event_type.upper()}] {message}")

        # Attempt to write to Neo4j, but don't let DB errors bubble up
        try:
            if not getattr(self, "_available", False) or getattr(self, "driver", None) is None:
                return
            import uuid
            event_id = str(uuid.uuid4())
            with self.driver.session() as session:
                session.run("""
                    CREATE (e:Event {
                        id: $event_id,
                        type:$event_type,
                        message:$message,
                        metadata:$metadata,
                        timestamp:datetime()
                    })
                """, event_id=event_id, event_type=event_type, message=message,
                     metadata=json.dumps(metadata or {}))
        except Exception as e:
            # Log the failure locally and continue; avoids crashing during startup
            logging.warning(f"Failed to write Event to Neo4j (skipping): {e}")

    # Helper to normalize values returned from Neo4j (datetimes etc.)
    def _normalize_value(self, v):
        # Convert neo4j DateTime or python datetime to ISO string
        try:
            if v is None:
                return None
            # neo4j.time.DateTime and datetime both implement isoformat
            if hasattr(v, "isoformat"):
                return v.isoformat()
            # fallback: try to call to_native() then isoformat
            if hasattr(v, "to_native"):
                nv = v.to_native()
                if hasattr(nv, "isoformat"):
                    return nv.isoformat()
            return v
        except Exception:
            return v

    # =====================================================
    # === POLICY MANAGEMENT ===============================
    # =====================================================
    def reload_policy(self):
        """Reload severity policy rules from YAML file."""
        try:
            with open(self.policy_file, "r") as f:
                self.policy = yaml.safe_load(f) or {}
            # Use local logging during init to avoid depending on DB availability
            logging.info(f"Reloaded severity policy from {self.policy_file}")
        except FileNotFoundError:
            logging.warning(f"Severity policy file not found at {self.policy_file}; using empty policy.")
            self.policy = {}
        except Exception as e:
            logging.exception(f"Failed to load severity policy from {self.policy_file}: {e}")
            self.policy = {}

    # =====================================================
    # === WORKFLOW MANAGEMENT =============================
    # =====================================================
    def load_workflow(self, workflow_id: str) -> Dict[str, Any]:
        """
        Try to load agents and NEXT edges from the DB.
        Returns a dict keyed by agent id with fields: id, name, type, next (list of {target, probability}).
        If DB not available or empty, return a default demo workflow.
        """
        workflow: Dict[str, Any] = {}
        if not getattr(self, "driver", None):
            return self._default_workflow()

        try:
            with self.driver.session() as session:
                q = """
                MATCH (w:Workflow {id:$workflow_id})-[:CAN_HANDLE]->(a:Agent)
                OPTIONAL MATCH (a)-[r:NEXT]->(b:Agent)
                RETURN a.id AS id, a.name AS name,
                       collect(
                         CASE WHEN b IS NULL THEN NULL
                              ELSE {
                                target: b.id,
                                probability: coalesce(r.probability, 0.1),
                                condition: CASE WHEN r.condition IS NOT NULL THEN r.condition ELSE '' END
                              }
                         END
                       ) AS next
                """
                for rec in session.run(q, workflow_id=workflow_id):
                    aid = rec.get("id") or rec.get("name")
                    next_list = [n for n in rec.get("next", []) if n is not None]
                    workflow[aid] = {"id": aid, "name": rec.get("name") or aid, "type": "generic", "next": next_list}
            if not workflow:
                return self._default_workflow()
            return workflow
        except Exception:
            logger.exception("Failed to load workflow from Neo4j, returning default")
            return self._default_workflow()

    def _default_workflow(self):
        """Return a default demo workflow when Neo4j is not available."""
        return {
            "agent_validator": {
                "id": "agent_validator",
                "name": "Validator Agent",
                "type": "generic",
                "next": [
                    {"target": "agent_executor", "probability": 0.8},
                    {"target": "agent_auditor", "probability": 0.2}
                ]
            },
            "agent_executor": {
                "id": "agent_executor", 
                "name": "Executor Agent",
                "type": "generic",
                "next": [
                    {"target": "agent_auditor", "probability": 1.0}
                ]
            },
            "agent_auditor": {
                "id": "agent_auditor",
                "name": "Auditor Agent", 
                "type": "generic",
                "next": []
            }
        }

    # =====================================================
    # === EXECUTION TRACE MANAGEMENT ======================
    # =====================================================
    def save_execution_trace(self, trace_id, workflow_id, agent_id, status, details):
        """Save an execution trace of a workflow step."""
        try:
            if getattr(self, "driver", None) is None:
                logging.warning("No Neo4j driver available; save_execution_trace skipped.")
                return
            with self.driver.session() as session:
                session.run("""
                    MERGE (t:ExecutionTrace {id:$trace_id})
                    SET t.workflow_id=$workflow_id,
                        t.agent_id=$agent_id,
                        t.status=$status,
                        t.details=$details,
                        t.timestamp=datetime()
                """, trace_id=trace_id, workflow_id=workflow_id,
                     agent_id=agent_id, status=status,
                     details=json.dumps(details))
            try:
                self.log_event("trace", f"Execution trace saved for {agent_id}", {
                    "trace_id": trace_id, "workflow_id": workflow_id, "status": status
                })
            except Exception:
                pass
        except Exception as e:
            logging.warning(f"Failed to save execution trace {trace_id}: {e}")

    # =====================================================
    # === DECISION MANAGEMENT =============================
    # =====================================================
    def save_decision(self, decision_id, agent, step, recommendation, tools, stats, explanations, severity, status="pending"):
        """Save or update a decision node in Neo4j."""
        try:
            if getattr(self, "driver", None) is None:
                logging.warning("No Neo4j driver available; save_decision skipped.")
                return
            with self.driver.session() as session:
                session.run("""
                    MERGE (d:Decision {id:$id})
                    SET d.agent=$agent,
                        d.step=$step,
                        d.recommendation=$recommendation,
                        d.tools=$tools,
                        d.stats=$stats,
                        d.explanations=$explanations,
                        d.severity=$severity,
                        d.status=$status,
                        d.created_at=datetime()
                """, id=decision_id,
                     agent=agent, step=step,
                     recommendation=recommendation,
                     tools=json.dumps(tools),
                     stats=json.dumps(stats),
                     explanations=json.dumps(explanations),
                     severity=severity, status=status)
            try:
                self.log_event("decision", f"Decision saved ({decision_id})", {
                    "agent": agent, "step": step, "severity": severity, "status": status
                })
            except Exception:
                pass
        except Exception as e:
            logging.warning(f"Failed to save decision {decision_id}: {e}")

    def resolve_decision(self, decision_id, choice, status="approved", resolved_by="admin"):
        """Resolve a decision with metadata (who resolved it)."""
        try:
            if getattr(self, "driver", None) is None:
                logging.warning("No Neo4j driver available; resolve_decision skipped.")
                return
            with self.driver.session() as session:
                session.run("""
                    MATCH (d:Decision {id:$id})
                    SET d.status=$status,
                        d.choice=$choice,
                        d.resolved_by=$resolved_by,
                        d.resolved_at=datetime()
                """, id=decision_id, choice=choice, status=status, resolved_by=resolved_by)
            try:
                self.log_event("decision", f"Decision {decision_id} resolved by {resolved_by}", {
                    "choice": choice, "status": status
                })
            except Exception:
                pass
        except Exception as e:
            logging.warning(f"Failed to resolve decision {decision_id}: {e}")

    def get_decision_queue(self, limit=50, severity=None, auto_apply_policy=True):
        """
        Fetch pending decisions.
        Applies policy auto-approvals when enabled.
        """
        query = """
        MATCH (d:Decision {status:'pending'})
        """
        if severity:
            query += "WHERE d.severity=$severity\n"

        query += """
        RETURN d.id as id, d.agent as agent, d.step as step,
               d.recommendation as recommendation,
               d.tools as tools, d.stats as stats,
               d.explanations as explanations, d.severity as severity,
               d.created_at as created_at
        ORDER BY d.created_at ASC
        LIMIT $limit
        """

        try:
            if getattr(self, "driver", None) is None:
                logging.warning("No Neo4j driver available; get_decision_queue returning empty list.")
                return []
            with self.driver.session() as session:
                results = session.run(query, limit=limit, severity=severity)
                queue = []

                for r in results:
                    # guard JSON fields in case of NULLs
                    tools_blob = r.get("tools") or "[]"
                    stats_blob = r.get("stats") or "[]"
                    explanations_blob = r.get("explanations") or "{}"

                    try:
                        tools_val = json.loads(tools_blob)
                    except Exception:
                        tools_val = []
                    try:
                        stats_val = json.loads(stats_blob)
                    except Exception:
                        stats_val = []
                    try:
                        explanations_val = json.loads(explanations_blob)
                    except Exception:
                        explanations_val = {}

                    decision = {
                        "id": r["id"],
                        "agent": r["agent"],
                        "step": r["step"],
                        "recommendation": r["recommendation"],
                        "tools": tools_val,
                        "stats": stats_val,
                        "explanations": explanations_val,
                        "severity": r["severity"],
                        "created_at": self._normalize_value(r.get("created_at")),
                    }

                    # Apply auto-approval policy
                    if auto_apply_policy and decision["severity"] in self.policy.get("severity_levels", {}):
                        rules = self.policy["severity_levels"][decision["severity"]]
                        if rules.get("auto_approve", False):
                            try:
                                self.resolve_decision(
                                    decision_id=decision["id"],
                                    choice=decision["recommendation"],
                                    status="auto_approved",
                                    resolved_by="policy"
                                )
                                try:
                                    self.log_event("decision", f"Auto-approved decision {decision['id']} via policy", decision)
                                except Exception:
                                    pass
                            except Exception as e:
                                logging.warning(f"Failed to auto-approve decision {decision['id']}: {e}")
                            continue

                    queue.append(decision)

                return queue
        except Exception as e:
            logging.warning(f"Failed to fetch decision queue: {e}")
            return []

    # =====================================================
    # === FEEDBACK & LEARNING =============================
    # =====================================================
    def add_fallback_edge(self, from_agent, to_agent, similarity_score):
        """Add semantic fallback edge from vector similarity search."""
        try:
            if getattr(self, "driver", None) is None:
                logging.warning("No Neo4j driver available; add_fallback_edge skipped.")
                return
            with self.driver.session() as session:
                session.run("""
                    MATCH (a:Agent {id:$from_agent}), (b:Agent {id:$to_agent})
                    MERGE (a)-[n:NEXT]->(b)
                    ON CREATE SET n.probability=$prob, n.learned=true, n.uses=1
                    ON MATCH SET n.probability = n.probability + $prob, n.uses = coalesce(n.uses,0) + 1
                """, from_agent=from_agent, to_agent=to_agent,
                     prob=similarity_score)
            try:
                self.log_event("feedback", f"Fallback edge {from_agent} -> {to_agent} added/updated", {
                    "similarity_score": similarity_score
                })
            except Exception:
                pass
        except Exception as e:
            logging.warning(f"Failed to add/update fallback edge {from_agent}->{to_agent}: {e}")

    def decay_edges(self, decay_rate=0.05):
        """Decay probability of unused learned edges over time."""
        try:
            if getattr(self, "driver", None) is None:
                logging.warning("No Neo4j driver available; decay_edges skipped.")
                return
            with self.driver.session() as session:
                session.run("""
                    MATCH ()-[n:NEXT]->()
                    WHERE n.learned = true
                    SET n.probability = n.probability * (1 - $decay_rate)
                """, decay_rate=decay_rate)
            try:
                self.log_event("feedback", "Decayed learned edges", {"decay_rate": decay_rate})
            except Exception:
                pass
        except Exception as e:
            logging.warning(f"Failed to decay edges: {e}")


    def update_edge_feedback(self, from_agent, to_agent, success=True, reinforce=0.1, decay=0.1):
        """Reinforce successful paths, decay failed ones (RL-style)."""
        try:
            if getattr(self, "driver", None) is None:
                logging.warning("No Neo4j driver available; update_edge_feedback skipped.")
                return
            with self.driver.session() as session:
                if success:
                    session.run("""
                        MATCH (a:Agent {id:$from_agent})-[n:NEXT]->(b:Agent {id:$to_agent})
                        SET n.probability = n.probability + $reinforce
                    """, from_agent=from_agent, to_agent=to_agent, reinforce=reinforce)
                    try:
                        self.log_event("feedback", f"Reinforced edge {from_agent}->{to_agent}", {"reinforce": reinforce})
                    except Exception:
                        pass
                else:
                    session.run("""
                        MATCH (a:Agent {id:$from_agent})-[n:NEXT]->(b:Agent {id:$to_agent})
                        SET n.probability = n.probability * (1 - $decay)
                    """, from_agent=from_agent, to_agent=to_agent, decay=decay)
                    try:
                        self.log_event("feedback", f"Decayed edge {from_agent}->{to_agent}", {"decay": decay})
                    except Exception:
                        pass
        except Exception as e:
            logging.warning(f"Failed to update edge feedback {from_agent}->{to_agent}: {e}")


# =========================================================
# === Example Usage =======================================
# =========================================================
if __name__ == "__main__":
    # Example: credentials can be supplied via environment variables
    connector = Neo4jConnector()

    print(f"Neo4j available: {getattr(connector, '_available', False)}")

    print("🔄 Loading workflow...")
    wf = connector.load_workflow("workflow_demo")
    print("Loaded workflow:", wf)

    print("💾 Saving execution trace...")
    connector.save_execution_trace(
        trace_id="trace_001",
        workflow_id="workflow_demo",
        agent_id="agent_validator",
        status="success",
        details={"output": "Validated successfully"}
    )

    print("💾 Saving decision (low severity)...")
    connector.save_decision(
        decision_id="decision_002",
        agent="Executor",
        step="file_upload",
        recommendation="RPA_Tool",
        tools=["API_Tool", "RPA_Tool"],
        stats=[{"tool":"API_Tool","success_rate":0.9},{"tool":"RPA_Tool","success_rate":0.7}],
        explanations={"API_Tool":"Stable","RPA_Tool":"Some errors"},
        severity="low"
    )

    print("📥 Fetching queue (policy auto-applies)...")
    queue = connector.get_decision_queue()
    for d in queue:
        print("Pending:", d)

    print("⚠️ Fetching only HIGH severity decisions...")
    high_queue = connector.get_decision_queue(severity="high")
    for d in high_queue:
        print("High severity pending:", d)

    print("🙋 Manually resolving a decision...")
    if queue:
        connector.resolve_decision(
            decision_id=queue[0]["id"],
            choice="API_Tool",
            status="approved",
            resolved_by="admin"
        )

    connector.close()
    print("✅ Neo4jConnector test run complete.")

    # =====================================================
    # === AUDIT: DOCUMENT / STATEMENT / LINEITEM ==========
    # =====================================================
    def create_document_node(self, doc_id, name, doc_type, period, source):
        with self.driver.session() as session:
            session.run("""
                MERGE (d:Document {id: $doc_id})
                SET d.name = $name,
                    d.type = $doc_type,
                    d.period = $period,
                    d.source = $source
            """, doc_id=doc_id, name=name, doc_type=doc_type, period=period, source=source)

    def create_statement_node(self, stmt_id, stmt_type, period, doc_id):
        with self.driver.session() as session:
            session.run("""
                MATCH (d:Document {id: $doc_id})
                MERGE (s:Statement {id: $stmt_id})
                SET s.type = $stmt_type,
                    s.period = $period
                MERGE (d)-[:CONTAINS]->(s)
            """, stmt_id=stmt_id, stmt_type=stmt_type, period=period, doc_id=doc_id)

    def create_lineitem_node(self, li_id, name, value, currency, stmt_id):
        with self.driver.session() as session:
            session.run("""
                MATCH (s:Statement {id: $stmt_id})
                MERGE (l:LineItem {id: $li_id})
                SET l.name = $name,
                    l.value = $value,
                    l.currency = $currency
                MERGE (s)-[:HAS_ITEM]->(l)
            """, li_id=li_id, name=name, value=value, currency=currency, stmt_id=stmt_id)

    # =====================================================
    # === AUDIT: RULES + FINDINGS =========================
    # =====================================================
    def get_all_rules(self):
        """Return all Rule nodes as dicts."""
        if not getattr(self, "driver", None):
            return []
        try:
            with self.driver.session() as session:
                result = session.run(
                    "MATCH (r:Rule) RETURN r.id as id, r.description as description, r.severity as severity"
                )
                return [dict(record) for record in result]
        except Exception:
            logger.exception("Failed to fetch rules from Neo4j")
            return []

    def get_lineitems_by_name(self, name):
        """Return LineItem nodes matching name."""
        if not getattr(self, "driver", None):
            return []
        try:
            with self.driver.session() as session:
                result = session.run(
                    "MATCH (l:LineItem {name: $name}) RETURN l.id as id, l.name as name, l.value as value, l.currency as currency",
                    name=name,
                )
                return [dict(record) for record in result]
        except Exception:
            logger.exception("Failed to fetch lineitems for name=%s", name)
            return []

    def create_finding_node(self, finding_id, finding_type, message, status, rule_id, lineitem_id):
        """Create a Finding node and link it to the Rule and LineItem."""
        if not getattr(self, "driver", None):
            return
        try:
            with self.driver.session() as session:
                session.run(
                    """
                    MATCH (r:Rule {id: $rule_id})
                    MATCH (l:LineItem {id: $lineitem_id})
                    MERGE (f:Finding {id: $finding_id})
                    SET f.type = $finding_type,
                        f.message = $message,
                        f.status = $status, f.ts = $ts
                    MERGE (f)-[:VIOLATES]->(r)
                    MERGE (f)-[:FOUND_IN]->(l)
                    """,
                    finding_id=finding_id,
                    finding_type=finding_type,
                    message=message,
                    status=status,
                    rule_id=rule_id,
                    lineitem_id=lineitem_id,
                    ts=datetime.utcnow().isoformat(),
                )
        except Exception:
            logger.exception(
                "Failed to create finding %s for rule=%s lineitem=%s", finding_id, rule_id, lineitem_id
            )

    # =====================================================
    # === AUDIT: FINDINGS RETRIEVAL =======================
    # =====================================================
    def get_all_findings(self):
        """Return all Findings joined with Rule and LineItem metadata."""
        if not getattr(self, "driver", None):
            return []
        try:
            with self.driver.session() as session:
                result = session.run(
                    """
                    MATCH (f:Finding)-[:VIOLATES]->(r:Rule),
                          (f)-[:FOUND_IN]->(l:LineItem)
                    RETURN f.id as id,
                           f.type as type,
                           f.message as message,
                           f.status as status,
                           r.description as rule,
                           r.severity as severity,
                           l.name as lineitem,
                           l.value as value,
                           l.currency as currency,
                           f.ts as ts
                    """
                )
                rows = [dict(record) for record in result]
                # normalize timestamp values if present
                for row in rows:
                    if "ts" in row:
                        row["ts"] = self._normalize_value(row["ts"])
                return rows
        except Exception:
            logger.exception("Failed to fetch findings from Neo4j")
            return []
