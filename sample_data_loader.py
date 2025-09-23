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
        while current:
            step += 1
            neo.record_execution_trace(trace_id, current, step, success=True)
            if current == "Reader":
                next_agent = "Validator"
            elif current == "Validator":
                next_agent = random.choices(["ERP","Communicator"], weights=[0.7,0.3])[0]
            else:
                next_agent = None
            current = next_agent
        # Occasionally add fallback edges
        if random.random() < 0.3:
            src = random.choice(agents)
            dst = random.choice([a for a in agents if a != src])
            neo.stage_fallback_edge(src, dst, trace_id, prob=0.1)
    neo.close()

if __name__ == "__main__":
    load_sample_data(50)
    print("Sample dataset loaded into Neo4j.")
