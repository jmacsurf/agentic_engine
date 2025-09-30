import unittest
from unittest.mock import MagicMock, patch
import os

from neo4j_connector import Neo4jConnector

class TestNeo4jConnectorUnavailable(unittest.TestCase):
    def test_unavailable_flag_and_methods(self):
        # Force driver creation to fail by setting env to an invalid uri
        with patch.dict(os.environ, {"NEO4J_URI": "bolt://invalid:1234", "NEO4J_USER": "no", "NEO4J_PASSWORD": "no"}):
            # Patch GraphDatabase.driver to raise
            with patch("neo4j_connector.GraphDatabase.driver", side_effect=Exception("connect fail")):
                c = Neo4jConnector()
                self.assertFalse(getattr(c, "_available", True))
                # Methods should not raise and should return safe defaults
                self.assertEqual(c.load_workflow("x"), {})
                self.assertEqual(c.get_decision_queue(), [])
                c.save_execution_trace("t","w","a","s",{"k":"v"})
                c.save_decision("d","a","s","rec",[],[],{},"low")
                c.resolve_decision("d","choice")
                c.add_fallback_edge("a","b",0.5)
                c.decay_edges()
                c.update_edge_feedback("a","b", True)

class TestNeo4jConnectorMockedHappyPath(unittest.TestCase):
    def test_load_workflow_and_decisions(self):
        # Create a mock driver/session/run that returns controlled records
        mock_session = MagicMock()
        # Mock result rows for workflow
        mock_record = {"agent_id":"a1","name":"Agent1","type":"type","next_agents":[]}
        mock_result = [mock_record]
        mock_session.run.return_value = mock_result

        mock_driver = MagicMock()
        mock_driver.session.return_value.__enter__.return_value = mock_session

        with patch("neo4j_connector.GraphDatabase.driver", return_value=mock_driver):
            c = Neo4jConnector()
            # driver should be available
            self.assertTrue(getattr(c, "_available", False))
            wf = c.load_workflow("wf")
            self.assertIn("a1", wf)

if __name__ == '__main__':
    unittest.main()
