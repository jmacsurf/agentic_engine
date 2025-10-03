"""
neo4j_migration.py

Migration utility for Agentic Engine.
- Creates Neo4j schema constraints and indexes
- Seeds demo data (agents, workflow, decisions, traces, events)
- Provides rollback() and reset() for development/testing
- Integrates ToolManager so Decision nodes always list available tools
"""

from neo4j import GraphDatabase
from tools.tool_manager import ToolManager

# =========================================================
# === CONFIGURATION =======================================
# =========================================================
NEO4J_URI = "bolt://localhost:7687"
NEO4J_USER = "neo4j"
NEO4J_PASSWORD = "test"

TEST_NEO4J_URI = "bolt://localhost:7688"  # Example test DB (Docker, CI, etc.)

# =========================================================
# === MIGRATION CLASS =====================================
# =========================================================
class Neo4jMigration:
    def __init__(self, uri=None, user=NEO4J_USER, password=NEO4J_PASSWORD, test=False):
        """
        Initialize Neo4j driver connection.
        If test=True, connects to TEST_NEO4J_URI.
        """
        if test:
            self.uri = uri or TEST_NEO4J_URI
            print("⚠️ TEST MODE ENABLED — using test database at", self.uri)
        else:
            self.uri = uri or NEO4J_URI

        self.driver = GraphDatabase.driver(self.uri, auth=(user, password))
        self.tool_manager = ToolManager()  # Load tools from config

    def close(self):
        """Close Neo4j driver connection."""
        self.driver.close()

    def run(self, query, **params):
        """Helper to run Cypher queries."""
        with self.driver.session() as session:
            return session.run(query, **params)

    # =====================================================
    # === MIGRATE: CREATE SCHEMA + SEED DEMO DATA ==========
    # =====================================================
    def migrate(self):
        """Create constraints and seed demo data."""
        print(f"🚀 Running Neo4j migration on {self.uri}...")

        # --- SCHEMA ---
        print("🔧 Creating constraints...")
        self.run("CREATE CONSTRAINT IF NOT EXISTS FOR (a:Agent) REQUIRE a.id IS UNIQUE")
        self.run("CREATE CONSTRAINT IF NOT EXISTS FOR (w:Workflow) REQUIRE w.id IS UNIQUE")
        self.run("CREATE CONSTRAINT IF NOT EXISTS FOR (d:Decision) REQUIRE d.id IS UNIQUE")
        self.run("CREATE CONSTRAINT IF NOT EXISTS FOR (t:ExecutionTrace) REQUIRE t.id IS UNIQUE")
        self.run("CREATE CONSTRAINT IF NOT EXISTS FOR (e:Event) REQUIRE e.id IS UNIQUE")

        # --- AGENTS ---
        print("👷 Creating sample agents...")
        agents = [
            {"id": "agent_validator", "name": "Validator", "type": "validation"},
            {"id": "agent_executor", "name": "Executor", "type": "execution"},
            {"id": "agent_auditor", "name": "Auditor", "type": "audit"}
        ]
        for agent in agents:
            self.run(
                "MERGE (a:Agent {id:$id}) "
                "SET a.name=$name, a.type=$type",
                **agent
            )

        # --- WORKFLOW ---
        print("📦 Creating sample workflow...")
        workflow = {"id": "workflow_demo", "name": "Demo Workflow"}
        self.run(
            "MERGE (w:Workflow {id:$id}) "
            "SET w.name=$name",
            **workflow
        )
        self.run("""
        MATCH (w:Workflow {id:'workflow_demo'})
        MATCH (v:Agent {id:'agent_validator'})
        MATCH (e:Agent {id:'agent_executor'})
        MATCH (a:Agent {id:'agent_auditor'})
        MERGE (w)-[:CAN_HANDLE]->(v)
        MERGE (v)-[:NEXT {probability:0.8}]->(e)
        MERGE (v)-[:NEXT {probability:0.2}]->(a)
        MERGE (e)-[:NEXT {probability:1.0}]->(a)
        """)

        # --- DECISIONS ---
        print("📝 Creating sample decisions...")
        available_tools = self.tool_manager.list_tools()

        decisions = [
            {
                "id": "decision_001",
                "agent": "Validator",
                "step": "data_entry",
                "recommendation": "API_Tool",
                "tools": str(available_tools),
                "stats": '[{"tool":"API_Tool","success_rate":0.85}]',
                "explanations": '{"API_Tool":"High reliability"}',
                "severity": "medium",
                "status": "pending",
            },
            {
                "id": "decision_002",
                "agent": "Executor",
                "step": "file_upload",
                "recommendation": "RPA_Tool",
                "tools": str(available_tools),
                "stats": '[{"tool":"API_Tool","success_rate":0.9}]',
                "explanations": '{"API_Tool":"High throughput"}',
                "severity": "low",
                "status": "pending",
            },
            {
                "id": "decision_003",
                "agent": "Auditor",
                "step": "financial_transaction",
                "recommendation": "API_Tool",
                "tools": str(available_tools),
                "stats": '[{"tool":"API_Tool","success_rate":0.95}]',
                "explanations": '{"API_Tool":"Preferred for reliability"}',
                "severity": "high",
                "status": "pending",
            }
        ]
        for decision in decisions:
            self.run("""
            MERGE (d:Decision {id:$id})
            SET d.agent=$agent, d.step=$step,
                d.recommendation=$recommendation,
                d.tools=$tools, d.stats=$stats,
                d.explanations=$explanations,
                d.severity=$severity, d.status=$status,
                d.created_at=datetime()
            """, **decision)

        # --- EXECUTION TRACE ---
        print("📊 Creating sample execution trace...")
        self.run("""
        MERGE (t:ExecutionTrace {id:'trace_001'})
        SET t.workflow_id='workflow_demo',
            t.agent_id='agent_validator',
            t.status='success',
            t.details='{"output": "Validated successfully"}',
            t.timestamp=datetime()
        """)

        # --- EVENTS ---
        print("📜 Creating sample events...")
        events = [
            {
                "type": "policy",
                "message": "Severity policy loaded",
                "metadata": '{"file":"config/severity_policy.yaml"}'
            },
            {
                "type": "decision",
                "message": "Decision decision_002 auto-approved by policy",
                "metadata": '{"decision_id":"decision_002","severity":"low"}'
            },
            {
                "type": "trace",
                "message": "Execution trace saved for agent_validator",
                "metadata": '{"trace_id":"trace_001","workflow_id":"workflow_demo"}'
            }
        ]
        for e in events:
            self.run("""
            CREATE (evt:Event {
                id: apoc.create.uuid(),
                type:$type,
                message:$message,
                metadata:$metadata,
                timestamp:datetime()
            })
            """, **e)

        print("✅ Migration complete!")

    # =====================================================
    # === ROLLBACK + RESET ================================
    # =====================================================
    def rollback(self):
        """Delete demo data but keep schema."""
        print("🧹 Rolling back demo data (keeping schema)...")
        self.run("MATCH (a:Agent {id:'agent_validator'}) DETACH DELETE a")
        self.run("MATCH (a:Agent {id:'agent_executor'}) DETACH DELETE a")
        self.run("MATCH (a:Agent {id:'agent_auditor'}) DETACH DELETE a")
        self.run("MATCH (w:Workflow {id:'workflow_demo'}) DETACH DELETE w")
        self.run("MATCH (d:Decision) WHERE d.id STARTS WITH 'decision_' DETACH DELETE d")
        self.run("MATCH (t:ExecutionTrace {id:'trace_001'}) DETACH DELETE t")
        self.run("MATCH (e:Event) DETACH DELETE e")
        print("✅ Rollback complete!")

    def reset(self):
        """Rollback then reseed demo data."""
        print("🔄 Resetting graph...")
        self.rollback()
        self.migrate()
        print("✅ Reset complete!")

# =========================================================
# === RUN SCRIPT DIRECTLY =================================
# =========================================================
if __name__ == "__main__":
    migrator = Neo4jMigration()

    action = input("Type 'migrate', 'rollback', or 'reset': ").strip().lower()
    if action == "migrate":
        migrator.migrate()
    elif action == "rollback":
        migrator.rollback()
    elif action == "reset":
        migrator.reset()
    else:
        print("⚠️ Invalid action. Use 'migrate', 'rollback', or 'reset'.")

    migrator.close()

# =========================================================
# === AUDIT USE CASE SCHEMA MIGRATION ====================
# =========================================================

def migrate_audit_schema(driver):
    """
    Extend Neo4j schema for Audit use case:
    - Documents (PDF, Excel, Word)
    - Statements (Income, Balance, Cash Flow)
    - LineItems (values in statements)
    - Rules (compliance checks)
    - Findings (audit results)
    """
    with driver.session() as session:
        session.run("""
            // === Constraints ===
            CREATE CONSTRAINT document_id IF NOT EXISTS
            FOR (d:Document) REQUIRE d.id IS UNIQUE;

            CREATE CONSTRAINT statement_id IF NOT EXISTS
            FOR (s:Statement) REQUIRE s.id IS UNIQUE;

            CREATE CONSTRAINT lineitem_id IF NOT EXISTS
            FOR (l:LineItem) REQUIRE l.id IS UNIQUE;

            CREATE CONSTRAINT rule_id IF NOT EXISTS
            FOR (r:Rule) REQUIRE r.id IS UNIQUE;

            CREATE CONSTRAINT finding_id IF NOT EXISTS
            FOR (f:Finding) REQUIRE f.id IS UNIQUE;
        """)

        print("✅ Audit schema migration completed.")


def seed_audit_demo(driver):
    """
    Seed sample audit data for demo/testing.
    """
    with driver.session() as session:
        session.run("""
            CREATE (doc:Document {
                id: "doc1",
                name: "Q1_2024_Financials.pdf",
                type: "pdf",
                date: date("2024-03-31"),
                source: "ERP"
            });

            CREATE (stmt:Statement {
                id: "stmt1",
                type: "IncomeStatement",
                period: "FY2024-Q1"
            });

            CREATE (li:LineItem {
                id: "li1",
                name: "Revenue",
                value: 1000000,
                currency: "USD"
            });

            CREATE (rule:Rule {
                id: "rule1",
                description: "Revenue must be non-negative",
                severity: "high"
            });

            CREATE (finding:Finding {
                id: "f1",
                type: "Violation",
                message: "Negative revenue detected",
                status: "open"
            });

            // === Relationships ===
            CREATE (doc)-[:CONTAINS]->(stmt);
            CREATE (stmt)-[:HAS_ITEM]->(li);
            CREATE (rule)-[:APPLIES_TO]->(li);
            CREATE (finding)-[:VIOLATES]->(rule);
            CREATE (finding)-[:FOUND_IN]->(li);
            CREATE (finding)-[:DOCUMENTED_IN]->(doc);
        """)

        print("✅ Audit demo data seeded.")

# =========================================================
# === LANGGRAPH WORKFLOW SEEDING ==========================
# =========================================================
def seed_audit_langgraph_workflow(driver):
    """
    Create a simple DAG for audit workflow:
    Ingest -> Validate -> Report
    """

    with driver.session() as session:
        session.run("""
            // Clear old demo workflow if exists
            MATCH (w:Workflow {id: "audit_workflow"}) DETACH DELETE w;

            // Create workflow
            CREATE (w:Workflow {id: "audit_workflow", name: "Audit Workflow"});

            // Agents
            CREATE (a1:Agent {id: "ingest_agent", name: "Document Ingestor", type: "ingest"});
            CREATE (a2:Agent {id: "validate_agent", name: "Audit Validator", type: "validation"});
            CREATE (a3:Agent {id: "report_agent", name: "Audit Reporter", type: "report"});

            // Relationships
            CREATE (w)-[:STARTS_WITH]->(a1);
            CREATE (a1)-[:NEXT {probability: 1.0}]->(a2);
            CREATE (a2)-[:NEXT {probability: 1.0}]->(a3);
        """)

        print("✅ Seeded Audit LangGraph workflow (Ingest → Validate → Report).")

# =========================================================
# === MAIN (extend CLI options) ==========================
# =========================================================
if __name__ == "__main__":
    from neo4j import GraphDatabase

    uri = "bolt://localhost:7687"
    driver = GraphDatabase.driver(uri, auth=("neo4j", "password"))

    import sys
    if len(sys.argv) > 1:
        cmd = sys.argv[1]
        if cmd == "migrate_audit":
            migrate_audit_schema(driver)
        elif cmd == "seed_audit":
            seed_audit_demo(driver)
        else:
            print("Usage: python neo4j_migration.py [migrate|seed|migrate_audit|seed_audit]")
    else:
        print("Usage: python neo4j_migration.py [migrate|seed|migrate_audit|seed_audit]")

        elif cmd == "seed_audit_langgraph":
    seed_audit_langgraph_workflow(driver)
