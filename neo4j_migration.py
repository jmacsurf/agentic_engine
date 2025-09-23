
from neo4j import GraphDatabase

URI = "bolt://localhost:7687"
USER = "neo4j"
PASSWORD = "test"

MIGRATION_CYPHER = [
    "CREATE CONSTRAINT agent_name IF NOT EXISTS FOR (a:Agent) REQUIRE a.name IS UNIQUE",
    "CREATE CONSTRAINT exec_trace_id IF NOT EXISTS FOR (et:ExecutionTrace) REQUIRE et.id IS UNIQUE",
    "MERGE (r:Agent {name:'Reader'})",
    "MERGE (v:Agent {name:'Validator'})",
    "MERGE (e:Agent {name:'ERP'})",
    "MERGE (c:Agent {name:'Communicator'})",
    "MERGE (r)-[:NEXT {condition:'always', probability:1.0}]->(v)",
    "MERGE (v)-[:NEXT {condition:'valid', probability:0.8}]->(e)",
    "MERGE (v)-[:NEXT {condition:'invalid', probability:0.2}]->(c)"
]

def run_migration():
    driver = GraphDatabase.driver(URI, auth=(USER, PASSWORD))
    with driver.session() as session:
        for stmt in MIGRATION_CYPHER:
            session.run(stmt)
            print(f"Executed: {stmt}")
    driver.close()

if __name__ == "__main__":
    run_migration()
