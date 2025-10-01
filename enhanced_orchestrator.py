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

from neo4j_connector import Neo4jConnector
from tools.tool_manager import ToolManager


# =========================================================
# === ENHANCED ORCHESTRATOR (ASYNC) ======================
# =========================================================
class EnhancedOrchestrator:
    def __init__(self):
        """Initialize orchestrator with Neo4j connector, ToolManager, FAISS index."""
        self.connector = Neo4jConnector()
        self.tools = ToolManager()

        # get configured tool names (may be empty)
        self.tool_names = self.tools.list_tools() or []

        # If no tools configured, use a small fallback so embeddings code has data
        if not self.tool_names:
            logger.info("No tools found in ToolManager; using fallback tool names for embeddings")
            self.tool_names = ["API_Tool", "RPA_Tool"]

        # create embeddings (safe when tool_names is non-empty)
        self.embeddings = self._embed_tools(self.tool_names)

        # ensure embeddings is non-empty and has correct shape
        if self.embeddings is None or self.embeddings.size == 0:
            logger.warning("Embeddings empty; creating a minimal placeholder embedding")
            self.embeddings = np.zeros((1, 20), dtype="float32")
            self.tool_names = [self.tool_names[0]]

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
            explanations={"policy": f"Recommended {recommendation} for type {agent['type']}"},
            severity="medium"
        )

        # === Execute tool with fallback (async wrapper) ===
        result = await asyncio.to_thread(self.execute_with_fallback, agent, recommendation, decision_id)

        # === Save execution trace ===
        trace_id = f"trace_{uuid.uuid4()}"
        self.connector.save_execution_trace(
            trace_id=trace_id,
            workflow_id=workflow_id,
            agent_id=agent_id,
            status="success" if result["success"] else "failure",
            details=result
        )

        # === Probabilistic branching ===
        if agent["next"]:
            tasks = []
            for edge in agent["next"]:
                if random.random() < (edge["probability"] or 0):
                    tasks.append(self._run_agent_recursive(workflow, edge["target"], workflow_id))

            if tasks:
                await asyncio.gather(*tasks)

    # =====================================================
    # === TOOL RECOMMENDATION =============================
    # =====================================================
    def recommend_tool(self, agent):
        """Context-aware tool recommendation."""
        available = self.tools.list_tools()

        if agent["type"] == "validation":
            return "API_Tool" if "API_Tool" in available else random.choice(available)

        elif agent["type"] == "execution":
            if agent["name"].lower() == "file_upload" and "Selenium_RPA_Tool" in available:
                return "Selenium_RPA_Tool"
            return "RPA_Tool" if "RPA_Tool" in available else random.choice(available)

        elif agent["type"] == "audit":
            return "API_Tool" if "API_Tool" in available else random.choice(available)

        else:
            return random.choice(available)

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
        query_vec = self._embed(agent["name"])
        D, I = self.index.search(np.expand_dims(query_vec, axis=0), k=1)
        best_match = self.tool_names[I[0][0]]
        vector_result = self.tools.execute(best_match, {"agent": agent["name"], "step": agent["type"]})

        if vector_result["success"]:
            self.connector.resolve_decision(decision_id, choice=best_match, status="approved", resolved_by="vector")
            self.connector.add_fallback_edge(agent["id"], best_match, float(D[0][0]))
            return vector_result

        self.connector.resolve_decision(decision_id, choice=tool_name, status="rejected", resolved_by="system")
        return result


# =========================================================
# === MAIN RUNNER =========================================
# =========================================================
if __name__ == "__main__":
    orch = EnhancedOrchestrator()
    asyncio.run(orch.run_workflow("workflow_demo"))

