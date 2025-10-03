"""
audit_reporter_tool.py

AuditReporterTool for Audit Use Case.

Responsibilities:
- Retrieve audit Findings from Neo4j.
- Summarize by severity, rule violated, and affected LineItems.
- Export results in JSON or Markdown format for reporting.
"""

import json
import logging
from typing import List, Dict, Any, Optional

# tolerant import for connector (works whether package is top-level or nested)
try:
    from agentic_engine.neo4j_connector import Neo4jConnector
except Exception:
    from neo4j_connector import Neo4jConnector

logger = logging.getLogger(__name__)


# =========================================================
# === AUDIT REPORTER TOOL ================================
# =========================================================
class AuditReporterTool:
    def __init__(self):
        self.connector = Neo4jConnector()

    def get_findings(self, status: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Retrieve findings from Neo4j. If status provided, filter by f.status.
        Returns list of dicts with keys: id, type, message, status, rule_id, lineitem_id, ts
        """
        if not getattr(self.connector, "driver", None):
            logger.warning("Neo4j driver not available; returning empty findings")
            return []

        q = """
        MATCH (f:Finding)-[:VIOLATES]->(r:Rule), (f)-[:FOUND_IN]->(l:LineItem)
        RETURN f.id AS id, f.type AS type, f.message AS message, f.status AS status,
               r.id AS rule_id, r.description AS rule_description,
               l.id AS lineitem_id, l.name AS lineitem_name, f.ts AS ts
        """
        params = {}
        if status:
            q = q.replace("RETURN", "WHERE f.status = $status RETURN")
            params["status"] = status

        try:
            rows = self.connector.query(q, params)
            return rows
        except Exception:
            logger.exception("Failed to query findings")
            return []

    def summarize_findings(self, findings: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Return a summary: counts by status, by severity (if present in rule), and by rule.
        """
        summary = {"total": len(findings), "by_status": {}, "by_rule": {}}
        for f in findings:
            st = f.get("status") or "unknown"
            summary["by_status"].setdefault(st, 0)
            summary["by_status"][st] += 1

            rule = f.get("rule_description") or f.get("rule_id") or "unknown"
            entry = summary["by_rule"].setdefault(rule, {"count": 0, "examples": []})
            entry["count"] += 1
            if len(entry["examples"]) < 3:
                entry["examples"].append({"finding_id": f.get("id"), "message": f.get("message")})

        return summary

    def generate_report(self, output_format: str = "json", status: Optional[str] = None) -> str:
        """
        Generate an audit report from Findings in Neo4j.

        output_format: "json" or "markdown"

        Returns: str (report content)
        """
        findings = self.get_findings(status=status)

        if output_format == "json":
            return json.dumps(findings, indent=2)

        elif output_format == "markdown":
            report_lines = [
                "# 📊 Audit Report",
                "",
                f"Total Findings: {len(findings)}",
                ""
            ]
            severity_groups = {}
            for f in findings:
                sev = f.get("severity", "unknown")
                severity_groups.setdefault(sev, []).append(f)

            for sev, group in severity_groups.items():
                report_lines.append(f"## Severity: {sev} ({len(group)})")
                for f in group:
                    report_lines.append(f"- **Finding {f.get('id')}**: {f.get('message')} (LineItem: {f.get('lineitem')})")
                report_lines.append("")

            return "\n".join(report_lines)

        else:
            raise ValueError("Unsupported format. Use 'json' or 'markdown'.")

    def save_report(self, path: str, fmt: str = "json", status: Optional[str] = None) -> None:
        """
        Save report to disk.
        """
        try:
            content = self.generate_report(output_format=fmt, status=status)
            mode = "w"
            with open(path, mode, encoding="utf-8") as f:
                f.write(content)
            logger.info("Saved audit report to %s", path)
        except Exception:
            logger.exception("Failed to save report to %s", path)