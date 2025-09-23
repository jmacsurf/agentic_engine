from neo4j import GraphDatabase

class Neo4jConnector:
    def __init__(self, uri="bolt://localhost:7687", user="neo4j", password="testpassword123"):
        self.driver = GraphDatabase.driver(uri, auth=(user, password))

    def close(self):
        self.driver.close()

    def record_execution_trace(self, trace_id, agent, step, success=True):
        with self.driver.session() as session:
            session.run(
                "MERGE (et:ExecutionTrace {id:$tid}) "
                "SET et.timestamp=datetime(), et.success=$success "
                "MERGE (a:Agent {name:$agent}) "
                "MERGE (et)-[:USED_AGENT {step:$step}]->(a)",
                tid=trace_id, success=success, agent=agent, step=step)

    def get_next_edges(self, src_agent):
        query = "MATCH (a:Agent {name:$src})-[r:NEXT]->(b:Agent) RETURN b.name as target, r.probability as probability"
        with self.driver.session() as session:
            return [dict(rec) for rec in session.run(query, src=src_agent)]

    def reinforce_edge(self, src, dst, success=True):
        with self.driver.session() as session:
            if success:
                session.run("MATCH (a:Agent {name:$src})-[r:NEXT]->(b:Agent {name:$dst}) "
                            "SET r.probability = r.probability * 1.1, r.successes = coalesce(r.successes,0)+1",
                            src=src, dst=dst)
            else:
                session.run("MATCH (a:Agent {name:$src})-[r:NEXT]->(b:Agent {name:$dst}) "
                            "SET r.probability = r.probability * 0.9, r.failures = coalesce(r.failures,0)+1",
                            src=src, dst=dst)

    def stage_fallback_edge(self, src_agent, dst_agent, trace_id, prob=0.2):
        with self.driver.session() as session:
            session.run("MERGE (a:Agent {name:$src}) "
                        "MERGE (b:Agent {name:$dst}) "
                        "MERGE (a)-[r:PENDING_NEXT]->(b) "
                        "SET r.condition='any', r.probability=$prob, r.proposed_at=datetime()",
                        src=src_agent, dst=dst_agent, prob=prob)
