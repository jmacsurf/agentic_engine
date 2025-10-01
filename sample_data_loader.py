# ...existing code...
import random
import uuid
from neo4j_connector import Neo4jConnector

def load_sample_data(num_traces=20):
    neo = Neo4jConnector(password="testpassword123")
    agents = ["Reader", "Validator", "ERP", "Communicator"]
    for t in range(num_traces):
        trace_id = str(uuid.uuid4())
        step = 0
        current = "Reader"
        # new: provide a workflow_id and use the connector signature (trace_id, workflow_id, agent_id, status, details)
        workflow_id = "workflow_demo"
        while current:
            step += 1
            status = "success"
            details = {"step": step, "trace_index": t}
            neo.save_execution_trace(trace_id, workflow_id, current, status, details)
            if current == "Reader":
                next_agent = "Validator"
            elif current == "Validator":
                next_agent = random.choices(["ERP","Communicator"], weights=[0.7,0.3])[0]
            else:
                next_agent = None
            current = next_agent
        # Occasionally add fallback edges using add_fallback_edge(signature: from_agent, to_agent, similarity_score)
        if random.random() < 0.3:
            src = random.choice(agents)
            dst = random.choice([a for a in agents if a != src])
            neo.add_fallback_edge(src, dst, similarity_score=0.1)
    neo.close()

if __name__ == "__main__":
    load_sample_data(50)
    print("Sample dataset loaded into Neo4j.")
# ...existing code...