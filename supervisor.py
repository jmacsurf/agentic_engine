import uuid
import random
from neo4j_connector import Neo4jConnector
import requests

class Supervisor:
    def __init__(self, neo4j_uri="bolt://neo4j:7687", user="neo4j", password="testpassword", faiss_url="http://faiss:6000"):
        self.neo = Neo4jConnector(uri=neo4j_uri, user=user, password=password)
        self.faiss_url = faiss_url

    def run(self, input_data):
        trace_id = str(uuid.uuid4())
        print(f"[Supervisor] Starting workflow trace {trace_id}")

        # For demo: always start with Reader
        current = "Reader"
        step = 0
        success = True

        while current:
            print(f"[Supervisor] Step {step}: Executing {current}")
            step += 1

            # Record trace
            self.neo.record_execution_trace(trace_id, current, step, success=True)

            # Get next agent (probabilistic + semantic fallback)
            next_agent = self.get_next_agent(current, input_data, trace_id)
            if not next_agent:
                print("[Supervisor] No next agent found, stopping.")
                break

            current = next_agent

        print(f"[Supervisor] Workflow complete, trace={trace_id}")

    def get_next_agent(self, current, input_data, trace_id):
        edges = self.neo.get_next_edges(current)
        if edges:
            total = sum(e["probability"] for e in edges)
            r = random.uniform(0, total)
            upto = 0
            for e in edges:
                if upto + e["probability"] >= r:
                    self.neo.reinforce_edge(current, e["target"], success=True)
                    return e["target"]
                upto += e["probability"]

        print("[Supervisor] Falling back to semantic search...")
        query_vec = [0.1] * 384
        res = requests.post(f"{self.faiss_url}/search", json={"query": query_vec, "k": 1}).json()
        if res:
            target = res[0]["name"]
            self.neo.stage_fallback_edge(current, target, trace_id=trace_id, prob=0.2)
            return target
        return None

if __name__ == "__main__":
    sup = Supervisor()
    sup.run("demo input")
