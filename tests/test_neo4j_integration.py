import os
import time
import subprocess
import unittest
import socket
from contextlib import closing

class TestNeo4jIntegration(unittest.TestCase):
    def test_docker_neo4j(self):
        if os.getenv("RUN_INTEGRATION_TESTS") != "1":
            self.skipTest("Integration tests are disabled. Set RUN_INTEGRATION_TESTS=1 to enable.")

        # Check docker is available
        try:
            subprocess.run(["docker", "--version"], check=True, stdout=subprocess.DEVNULL)
        except Exception:
            self.skipTest("Docker not available")

        # Pull and run a temporary neo4j container
        container_name = "agentic_engine_test_neo4j"
        try:
            subprocess.run(["docker", "run", "-d", "--rm", "--name", container_name,
                            "-p", "7687:7687", "-e", "NEO4J_AUTH=neo4j/test", "neo4j:5.13"], check=True)
        except Exception as e:
            self.fail(f"Failed to start neo4j container: {e}")

        try:
            # Wait for bolt port
            timeout = 60
            start = time.time()
            while time.time() - start < timeout:
                with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as sock:
                    try:
                        sock.connect(("127.0.0.1", 7687))
                        break
                    except OSError:
                        time.sleep(1)
            else:
                self.fail("Neo4j did not start in time")

            # Now attempt to import and use the connector
            from neo4j_connector import Neo4jConnector
            c = Neo4jConnector(user="neo4j", password="test")
            self.assertTrue(getattr(c, "_available", False))
            # Try a simple call (should not raise)
            wf = c.load_workflow("nonexistent")
            self.assertIsInstance(wf, dict)
            c.close()
        finally:
            subprocess.run(["docker", "stop", container_name])

if __name__ == '__main__':
    unittest.main()
