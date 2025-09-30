"""
supervisor.py

Supervisor orchestrates workflows of agents and tools.
- Loads workflow dynamically from Neo4j
- Executes agents and their assigned tools
- Saves execution traces into Neo4j
- Creates Decision nodes for human/policy review
- Uses ToolManager for API/RPA execution
- Supports fallback if recommended tool fails
- Integrates vector-based fallback (FAISS)
- Stays in sync with tools_config.yaml (dynamic tools)
- Context-aware tool recommendation (task-based preferences)
"""

import random
import uuid
import faiss
import numpy as np
from agentic_engine.neo4j_connector import Neo4jConnector
from agentic_engine.tools.tool_manager import ToolManager

# =========================================================
# === SUPERVISOR CLASS ====================================
# =========================================================
class Supervisor:
    def __init__(self):
        """Initialize supervisor with Neo4j, tool manager, and FAISS index."""
        self.connector = Neo4jConnector()
        self.tools = ToolManager()

        # Initialize FAISS index for semantic fallback
        self.tool_names = self.tools.list_tools()
        self.embeddings = self._embed_tools(self.tool_names)
        dim = self.embeddings.shape[1]
        self.index = faiss.IndexFlatL2(dim)
        self.index.add(self.embeddings)

    # =====================================================
    # === EMBEDDING UTILS =================================
    # =====================================================
    def _embed(self, text: str) -> np.ndarray:
        """
        Simple embedding stub.
        Replace with production embeddings (OpenAI, HuggingFace, etc.).
        """
        return np.array([ord(c) for c in text[:20]] + [0] * (20 - len(text[:20]))).astype("float32")

    def _embed_tools(self, tool_names):
        """Generate embeddings for tool names."""
        return np.vstack([self._embed(name) for name in tool_names])

    # =====================================================
    # === WORKFLOW RUNNER =================================
    # =====================================================
    def run_workflow(self, workflow_id: str):
        """Run a workflow by ID."""
        print(f"🚀 Running workflow {workflow_id}")
        workflow = self.connector.load_workflow(workflow_id)

        if not workflow:
            print(f"⚠️ No workflow found for {workflow_id}")
            return

        current = list(workflow.keys())[0]  # Start with first agent

        while current:
            agent = workflow[current]
            print(f"⚡ Executing agent: {agent['name']} ({current})")

            # === Decision Creation ===
            decision_id = f"decision_{uuid.uuid4()}"
            recommendation = self.recommend_tool(agent)
            available_tools = self.tools.list_tools()  # Dynamic

            self.connector.save_decision(
                decision_id=decision_id,
                agent=agent["name"],
                step=agent["name"],
                recommendation=recommendation,
                tools=str(available_tools),
                stats=[],
                explanations={"policy": f"Recommended based on agent type and step '{agent['name']}'"},
                severity="medium"
            )

            # === Execute with fallback ===
            result = self.execute_with_fallback(agent, recommendation, decision_id)

            # === Save execution trace ===
            trace_id = f"trace_{uuid.uuid4()}"
            self.connector.save_execution_trace(
                trace_id=trace_id,
                workflow_id=workflow_id,
                agent_id=current,
                status="success" if result["success"] else "failure",
                details=result
            )

            # === Probabilistic branching ===
            if agent["next"]:
                next_agent = self.choose_next(agent["next"])
                current = next_agent
            else:
                current = None

    # =====================================================
    # === TOOL RECOMMENDATION ==============================
    # =====================================================
    def recommend_tool(self, agent):
        """
        Recommend a tool based on agent type and step context.
        Context-aware rules:
        - validation → API_Tool
        - execution/file_upload → prefer Selenium_RPA_Tool if available, else RPA_Tool
        - audit/financial → API_Tool
        - fallback → random tool
        """
        available = self.tools.list_tools()

        if agent["type"] == "validation":
            return "API_Tool" if "API_Tool" in available else random.choice(available)

        elif agent["type"] == "execution":
            # Prefer Selenium for file uploads
            if agent["name"].lower() == "file_upload" and "Selenium_RPA_Tool" in available:
                return "Selenium_RPA_Tool"
            return "RPA_Tool" if "RPA_Tool" in available else random.choice(available)

        elif agent["type"] == "audit":
            return "API_Tool" if "API_Tool" in available else random.choice(available)

        else:
            return random.choice(available)

    # =====================================================
    # === TOOL EXECUTION WITH FALLBACK =====================
    # =====================================================
    def execute_with_fallback(self, agent, tool_name, decision_id):
        """Execute recommended tool, fallback to alternatives, then vector-based search."""
        print(f"🔧 Executing {tool_name} for agent {agent['name']}")
        result = self.tools.execute(tool_name, {"agent": agent["name"], "step": agent["type"]})

        if result["success"]:
            print(f"✅ {tool_name} succeeded")
            self.connector.resolve_decision(decision_id, choice=tool_name, status="approved", resolved_by="policy")
            return result

        print(f"❌ {tool_name} failed: {result['error']}")

        # Deterministic fallback
        for fallback in self.tools.list_tools():
            if fallback != tool_name:
                print(f"↩️ Trying fallback tool: {fallback}")
                fallback_result = self.tools.execute(fallback, {"agent": agent["name"], "step": agent["type"]})
                if fallback_result["success"]:
                    print(f"✅ Fallback {fallback} succeeded")
                    self.connector.resolve_decision(decision_id, choice=fallback, status="approved", resolved_by="fallback")
                    return fallback_result

        # Vector-based fallback
        print("🧠 No deterministic fallback succeeded, trying vector-based match...")
        query_vec = self._embed(agent["name"])
        D, I = self.index.search(np.expand_dims(query_vec, axis=0), k=1)
        best_match = self.tool_names[I[0][0]]

        print(f"🔍 Vector-based fallback suggested: {best_match}")
        vector_result = self.tools.execute(best_match, {"agent": agent["name"], "step": agent["type"]})

        if vector_result["success"]:
            print(f"✅ Vector fallback {best_match} succeeded")
            self.connector.resolve_decision(decision_id, choice=best_match, status="approved", resolved_by="vector")
            self.connector.add_fallback_edge(from_agent=agent["id"], to_agent=best_match, similarity_score=float(D[0][0]))
            return vector_result

        # Everything failed
        print(f"💥 All tools failed for agent {agent['name']}")
        self.connector.resolve_decision(decision_id, choice=tool_name, status="rejected", resolved_by="system")
        return result

    # =====================================================
    # === PROBABILISTIC NEXT AGENT =========================
    # =====================================================
    def choose_next(self, edges):
        """Choose next agent based on probability weights in edges."""
        total_prob = sum([e["probability"] or 0 for e in edges])
        r = random.random() * total_prob
        upto = 0
        for e in edges:
            p = e["probability"] or 0
            if upto + p >= r:
                return e["target"]
            upto += p
        return None

# =========================================================
# === MAIN RUNNER =========================================
# =========================================================
if __name__ == "__main__":
    s = Supervisor()
    s.run_workflow("workflow_demo")
