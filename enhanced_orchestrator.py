"""
enhanced_orchestrator.py (Async Version)

Brain of the Agentic Engine with asyncio support.

Enhancements:
- Agents can be executed concurrently if multiple branches are active.
- Tool execution is non-blocking using asyncio + gather().
- Probabilistic branching still applies, but in async mode.
"""

import uuid
import random
import asyncio
import numpy as np
import faiss
import logging

logger = logging.getLogger(__name__)

from neo4j_connector import Neo4jConnector
from tools.tool_manager import ToolManager

# === wire concrete tools (tolerant imports for package vs flat layout) ===
try:
    from tools.document_ingest_tool import DocumentIngestTool
except Exception:
    from agentic_engine.tools.document_ingest_tool import DocumentIngestTool

try:
    from tools.audit_validator_tool import AuditValidatorTool
except Exception:
    from agentic_engine.tools.audit_validator_tool import AuditValidatorTool

try:
    from tools.audit_reporter_tool import AuditReporterTool
except Exception:
    from agentic_engine.tools.audit_reporter_tool import AuditReporterTool


# =========================================================
# === ENHANCED ORCHESTRATOR (ASYNC) ======================
# =========================================================
class EnhancedOrchestrator:
    def __init__(self):
        """Initialize orchestrator with Neo4j connector, ToolManager, FAISS index."""
        self.connector = Neo4jConnector()
        self.tools = ToolManager()

        # concrete tool instances for ingest -> validate -> report pipeline
        self.ingest_tool = DocumentIngestTool()
        self.validator_tool = AuditValidatorTool()
        self.reporter_tool = AuditReporterTool()

        # FAISS vector search index
        self.tool_names = self.tools.list_tools() or []
        self.embeddings = self._embed_tools(self.tool_names)
        if self.embeddings is None or self.embeddings.size == 0:
            logger.warning("Embeddings empty; creating a minimal placeholder embedding")
            self.embeddings = np.zeros((1, 20), dtype="float32")
            self.tool_names = [self.tool_names[0] if self.tool_names else "API_Tool"]
        dim = int(self.embeddings.shape[1])
        try:
            self.index = faiss.IndexFlatL2(dim)
            self.index.add(self.embeddings)
        except Exception as e:
            logger.warning("Failed to create FAISS index: %s -- continuing without index", e)
            self.index = None

    # =====================================================
    # === EMBEDDING UTILS (PLACEHOLDER) ==================
    # =====================================================
    def _embed(self, text: str):
        """Simple deterministic embedding stub (keeps size consistent)."""
        max_len = 20
        arr = [ord(c) for c in (text or "")[:max_len]]
        arr += [0] * (max_len - len(arr))
        return np.array(arr, dtype="float32")

    def _embed_tools(self, tool_names):
        """Return stacked embeddings; return a minimal placeholder if tool_names empty."""
        if not tool_names:
            return np.zeros((1, 20), dtype="float32")
        mats = []
        for name in tool_names:
            try:
                emb = self._embed(name)
                mats.append(emb.reshape(1, -1))
            except Exception as e:
                logger.warning("Failed to embed tool name %s: %s", name, e)
        if not mats:
            return np.zeros((1, 20), dtype="float32")
        return np.vstack(mats)

    # =====================================================
    # === MAIN ASYNC WORKFLOW RUNNER ======================
    # =====================================================
    async def run_workflow(self, workflow_id: str):
        """Run a workflow asynchronously."""
        print(f"🚀 Running workflow {workflow_id}")
        workflow = self.connector.load_workflow(workflow_id)

        if not workflow:
            print(f"⚠️ No workflow found for {workflow_id}")
            return

        current = list(workflow.keys())[0]
        await self._run_agent_recursive(workflow, current, workflow_id)

    async def _run_agent_recursive(self, workflow, agent_id, workflow_id):
        """
        Recursively execute agents.
        If an agent has multiple next steps, run them concurrently.
        """
        # defensive checks: skip None targets and missing agents in workflow
        if agent_id is None:
            logger.debug("Agent target is None — end of branch.")
            return
        if agent_id not in workflow:
            logger.warning("Agent id '%s' not found in workflow — skipping branch.", agent_id)
            return
        agent = workflow[agent_id]
        print(f"⚡ Executing agent: {agent['name']} ({agent_id})")

        # === Create decision node ===
        decision_id = f"decision_{uuid.uuid4()}"
        recommendation = self.recommend_tool(agent)
        self.connector.save_decision(
            decision_id=decision_id,
            agent=agent["name"],
            step=agent["name"],
            recommendation=recommendation,
            tools=str(self.tools.list_tools()),
            stats=[],
            explanations={"policy": f"Recommended {recommendation} for type {agent.get('type')}"},
            severity="medium"
        )

        # === Pipeline wiring: Ingest -> Validate -> Report ===
        exec_result = None
        agent_type = agent.get("type", "").lower()

        try:
            if agent_type in ("ingest", "reader"):
                # use ingest tool; expect agent to optionally provide file_path
                params = agent.get("params") or {}
                file_path = params.get("file_path") or params.get("path") or "/tmp/demo_document.pdf"
                logger.info("Running DocumentIngestTool for %s", file_path)
                exec_result = await asyncio.to_thread(self.ingest_tool.ingest_document, file_path, params.get("doc_type", "pdf"), params.get("period", "FY2024-Q1"))
                # record tool execution
                self.connector.save_tool_execution(decision_id, agent_id, "DocumentIngestTool", exec_result or {})
            elif agent_type in ("validation", "validator"):
                logger.info("Running AuditValidatorTool")
                exec_result = await asyncio.to_thread(self.validator_tool.validate)
                # create findings saved via connector inside validator (if implemented)
                self.connector.save_tool_execution(decision_id, agent_id, "AuditValidatorTool", {"findings_count": len(exec_result) if exec_result is not None else 0})
            elif agent_type in ("report", "notify", "reporter", "audit_report"):
                logger.info("Running AuditReporterTool")
                fmt = agent.get("params", {}).get("format", "markdown")
                report = await asyncio.to_thread(self.reporter_tool.generate_report, "markdown" if fmt == "markdown" else "json")
                exec_result = {"report": report}
                # optionally persist report as an Event or blob node
                self.connector.log_event("report_generated", f"Report for workflow {workflow_id}", {"agent": agent_id, "format": fmt})
                self.connector.save_tool_execution(decision_id, agent_id, "AuditReporterTool", {"length": len(report)})
            else:
                # fallback to existing tool execution flow (ToolManager)
                logger.info("Falling back to ToolManager: executing recommended tool %s", recommendation)
                exec_result = await asyncio.to_thread(self.execute_with_fallback, agent, recommendation, decision_id)
        except Exception as e:
            logger.exception("Tool execution failed for agent %s: %s", agent_id, e)
            exec_result = {"success": False, "error": str(e)}

        # === Save execution trace ===
        trace_id = f"trace_{uuid.uuid4()}"
        self.connector.save_execution_trace(
            trace_id=trace_id,
            workflow_id=workflow_id,
            agent_id=agent_id,
            status="success" if (exec_result and exec_result.get("success", True)) else "failure",
            details=exec_result or {}
        )

        # === Probabilistic branching (unchanged) ===
        next_edges = agent.get("next") or []
        if next_edges:
            tasks = []
            for edge in next_edges:
                # normalize edge structure
                if not isinstance(edge, dict):
                    continue
                target = edge.get("target")
                prob = float(edge.get("probability") or 0.0)

                if not target:
                    logger.debug("Skipping None target for agent %s", agent_id)
                    continue
                if target not in workflow:
                    logger.warning("Skipping branch to unknown agent '%s' from '%s'", target, agent_id)
                    continue

                if random.random() < prob:
                    tasks.append(self._run_agent_recursive(workflow, target, workflow_id))

            if tasks:
                await asyncio.gather(*tasks)

    # =====================================================
    # === TOOL RECOMMENDATION =============================
    # =====================================================
    def recommend_tool(self, agent):
        """Context-aware tool recommendation."""
        available = self.tools.list_tools() or []

        # defensive fallback when ToolManager returns nothing
        if not available:
            logger.warning("No tools available from ToolManager; using fallback tools")
            available = ["API_Tool", "RPA_Tool"]

        if agent.get("type") == "validation":
            return "API_Tool" if "API_Tool" in available else available[0]

        if agent.get("type") == "execution":
            if agent.get("name", "").lower() == "file_upload" and "Selenium_RPA_Tool" in available:
                return "Selenium_RPA_Tool"
            return "RPA_Tool" if "RPA_Tool" in available else available[0]

        if agent.get("type") == "audit":
            return "API_Tool" if "API_Tool" in available else available[0]

        # default: return first available tool deterministically
        return available[0]

    # =====================================================
    # === TOOL EXECUTION WITH FALLBACK ====================
    # =====================================================
    def execute_with_fallback(self, agent, tool_name, decision_id):
        """Run tool with fallback (blocking, but async-wrapped by to_thread)."""
        print(f"🔧 Executing {tool_name} for agent {agent['name']}")
        result = self.tools.execute(tool_name, {"agent": agent["name"], "step": agent["type"]})

        if result["success"]:
            self.connector.resolve_decision(decision_id, choice=tool_name, status="approved", resolved_by="policy")
            return result

        # Fallback logic...
        for fallback in self.tools.list_tools():
            if fallback != tool_name:
                fallback_result = self.tools.execute(fallback, {"agent": agent["name"], "step": agent["type"]})
                if fallback_result["success"]:
                    self.connector.resolve_decision(decision_id, choice=fallback, status="approved", resolved_by="fallback")
                    return fallback_result

        # Vector-based fallback
        if self.index is not None and len(self.tool_names) > 0:
            query_vec = self._embed(agent["name"])
            D, I = self.index.search(np.expand_dims(query_vec, axis=0), k=1)
            if len(I) > 0 and len(I[0]) > 0:
                best_match = self.tool_names[I[0][0]]
                vector_result = self.tools.execute(best_match, {"agent": agent["name"], "step": agent["type"]})

                if vector_result["success"]:
                    self.connector.resolve_decision(decision_id, choice=best_match, status="approved", resolved_by="vector")
                    self.connector.add_fallback_edge(agent["id"], best_match, float(D[0][0]))
                    return vector_result
        
        # If no vector match available, return a basic success result
        self.connector.resolve_decision(decision_id, choice="default", status="completed", resolved_by="system")
        return result

    # =====================================================
    # === FULL AUDIT PIPELINE =============================
    # =====================================================
    async def run_audit_workflow(self, file_path: str, period: str = "FY2024-Q1", output_format: str = "markdown"):
        """
        End-to-end audit workflow:
        1. Ingest document into Neo4j
        2. Validate line items against rules
        3. Generate report

        Args:
            file_path: Path to the document (PDF/Excel) to ingest.
            period: Reporting period string.
            output_format: "json" or "markdown".

        Returns:
            dict with ingest summary, findings, and report.
        """

        # Step 1: Ingest
        self.connector.log_event("audit_ingest_start", f"Ingesting {file_path}", {"period": period})
        ingest_result = await asyncio.to_thread(self.ingest_tool.ingest_document, file_path, "pdf", period)

        # Step 2: Validate
        self.connector.log_event("audit_validate_start", f"Validating {file_path}", {"period": period})
        findings = await asyncio.to_thread(self.validator_tool.validate)

        # Step 3: Report
        self.connector.log_event("audit_report_start", f"Reporting for {file_path}", {"period": period})
        report = await asyncio.to_thread(self.reporter_tool.generate_report, output_format)

        return {
            "document": ingest_result,
            "findings": findings,
            "report": report
        }


# =========================================================
# === MAIN RUNNER =========================================
# =========================================================
if __name__ == "__main__":
    orch = EnhancedOrchestrator()
    asyncio.run(orch.run_workflow("workflow_demo"))

