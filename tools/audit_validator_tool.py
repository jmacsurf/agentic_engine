"""
audit_validator_tool.py

AuditValidatorTool for Audit Use Case.

Responsibilities:
- Query financial LineItems from Neo4j.
- Check them against Rule nodes (compliance/audit rules).
- Create Findings when violations occur.
"""

import uuid

# tolerant import for connector (works whether package is top-level or nested)
try:
    from agentic_engine.neo4j_connector import Neo4jConnector
except Exception:
    from neo4j_connector import Neo4jConnector


# =========================================================
# === AUDIT VALIDATOR TOOL ================================
# =========================================================
class AuditValidatorTool:
    def __init__(self):
        self.connector = Neo4jConnector()

    def validate(self):
        """
        Run audit validations:
        - Retrieve all rules from Neo4j.
        - Apply each rule against relevant LineItems or Statements.
        - Create Findings if violations are detected.

        Returns: list of findings created.
        """
        findings = []

        # === 1. Get all rules ===
        rules = self.connector.get_all_rules() if hasattr(self.connector, "get_all_rules") else []

        for rule in rules:
            rule_id = rule.get("id")
            desc = rule.get("description", "")
            severity = rule.get("severity", "medium")

            # === 2. Apply rule: simple example for Revenue non-negative ===
            if "Revenue must be non-negative" in desc:
                if hasattr(self.connector, "get_lineitems_by_name"):
                    lineitems = self.connector.get_lineitems_by_name("Revenue") or []
                else:
                    lineitems = []

                for li in lineitems:
                    if li.get("value", 0) < 0:
                        finding_id = f"f_{uuid.uuid4()}"
                        message = f"Rule Violation: {desc} → Found value {li.get('value')}"

                        if hasattr(self.connector, "create_finding_node"):
                            self.connector.create_finding_node(
                                finding_id=finding_id,
                                finding_type="Violation",
                                message=message,
                                status="open",
                                rule_id=rule_id,
                                lineitem_id=li.get("id")
                            )

                        findings.append({
                            "finding_id": finding_id,
                            "lineitem": li.get("name"),
                            "value": li.get("value"),
                            "rule": desc,
                            "severity": severity
                        })

        return findings

# filepath: tools/audit_validator_tool.py
"""
audit_validator_tool.py

AuditValidatorTool for Audit Use Case.

Responsibilities:
- Query financial LineItems from Neo4j.
- Check them against Rule nodes (compliance/audit rules).
- Create Findings when violations occur.
"""

import uuid

# tolerant import for connector (works whether package is top-level or nested)
try:
    from agentic_engine.neo4j_connector import Neo4jConnector
except Exception:
    from neo4j_connector import Neo4jConnector


# =========================================================
# === AUDIT VALIDATOR TOOL ================================
# =========================================================
class AuditValidatorTool:
    def __init__(self):
        self.connector = Neo4jConnector()

    def validate(self):
        """
        Run audit validations:
        - Retrieve all rules from Neo4j.
        - Apply each rule against relevant LineItems or Statements.
        - Create Findings if violations are detected.

        Returns: list of findings created.
        """
        findings = []

        # === 1. Get all rules ===
        rules = self.connector.get_all_rules() if hasattr(self.connector, "get_all_rules") else []

        for rule in rules:
            rule_id = rule.get("id")
            desc = rule.get("description", "")
            severity = rule.get("severity", "medium")

            # === 2. Apply rule: simple example for Revenue non-negative ===
            if "Revenue must be non-negative" in desc:
                if hasattr(self.connector, "get_lineitems_by_name"):
                    lineitems = self.connector.get_lineitems_by_name("Revenue") or []
                else:
                    lineitems = []

                for li in lineitems:
                    if li.get("value", 0) < 0:
                        finding_id = f"f_{uuid.uuid4()}"
                        message = f"Rule Violation: {desc} → Found value {li.get('value')}"

                        if hasattr(self.connector, "create_finding_node"):
                            self.connector.create_finding_node(
                                finding_id=finding_id,
                                finding_type="Violation",
                                message=message,
                                status="open",
                                rule_id=rule_id,
                                lineitem_id=li.get("id")
                            )

                        findings.append({
                            "finding_id": finding_id,
                            "lineitem": li.get("name"),
                            "value": li.get("value"),
                            "rule": desc,
                            "severity": severity
                        })

        return findings