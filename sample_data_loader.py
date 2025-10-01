# ...existing code...
import random
import uuid
from neo4j_connector import Neo4jConnector

def load_sample_data(num_traces=20):
    neo = Neo4jConnector(password="testpassword123")
    agents = ["Reader", "Validator", "ERP", "Communicator"]
    workflow_id = "workflow_demo"

    # Ensure Workflow and Agent nodes exist
    if getattr(neo, "driver", None) is not None:
        with neo.driver.session() as session:
            session.run("MERGE (w:Workflow {id:$workflow_id})", workflow_id=workflow_id)
            for a in agents:
                session.run("MERGE (ag:Agent {id:$id, name:$name})", id=a, name=a)
            # link workflow -> first agent as an entry point
            session.run("""
                MATCH (w:Workflow {id:$workflow_id}), (a:Agent {id:$entry})
                MERGE (w)-[:CAN_HANDLE]->(a)
            """, workflow_id=workflow_id, entry=agents[0])

    for t in range(num_traces):
        trace_id = str(uuid.uuid4())
        step = 0
        current = "Reader"

        while current:
            step += 1
            status = "success"
            details = {"step": step, "trace_index": t}
            # connector signature: trace_id, workflow_id, agent_id, status, details
            neo.save_execution_trace(trace_id, workflow_id, current, status, details)

            # Occasionally produce a decision at a step
            if random.random() < 0.15:
                decision_id = str(uuid.uuid4())
                neo.save_decision(
                    decision_id=decision_id,
                    agent=current,
                    step=step,
                    recommendation="use_api" if random.random() < 0.6 else "use_rpa",
                    tools=["API_Tool", "RPA_Tool"],
                    stats=[{"tool":"API_Tool","score":random.random()},{"tool":"RPA_Tool","score":random.random()}],
                    explanations={"note": f"auto-generated at step {step}"},
                    severity=random.choice(["low","medium","high"]),
                    status="pending"
                )

            # Basic workflow transitions
            if current == "Reader":
                next_agent = "Validator"
            elif current == "Validator":
                next_agent = random.choices(["ERP", "Communicator"], weights=[0.7, 0.3])[0]
            elif current == "ERP":
                # ERP usually finishes or passes to Communicator
                next_agent = random.choices(["Communicator", None], weights=[0.4, 0.6])[0]
            elif current == "Communicator":
                next_agent = None
            else:
                next_agent = None

            # create NEXT relationships with a small default probability if missing
            try:
                if getattr(neo, "driver", None) is not None and next_agent:
                    with neo.driver.session() as session:
                        session.run("""
                            MATCH (a:Agent {id:$from}), (b:Agent {id:$to})
                            MERGE (a)-[r:NEXT]->(b)
                            ON CREATE SET r.probability = coalesce(r.probability, 0.1)
                        """, from=current, to=next_agent)
            except Exception:
                pass

            current = next_agent

        # Occasionally add fallback edges between random agents
        if random.random() < 0.25:
            src = random.choice(agents)
            dst = random.choice([a for a in agents if a != src])
            neo.add_fallback_edge(src, dst, similarity_score=0.1)

    neo.close()

if __name__ == "__main__":
    load_sample_data(50)
    print("Sample dataset loaded into Neo4j.")
# ...existing code...