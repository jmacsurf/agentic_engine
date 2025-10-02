"""
document_ingest_tool.py

DocumentIngestTool for Audit Use Case.

Responsibilities:
- Parse financial documents (PDF, Excel).
- Extract Statements and LineItems.
- Store results in Neo4j (Document → Statement → LineItem graph).
"""

import uuid

# tolerant import for connector (works whether package is top-level or nested)
try:
    from agentic_engine.neo4j_connector import Neo4jConnector
except Exception:
    from neo4j_connector import Neo4jConnector


# =========================================================
# === DOCUMENT INGEST TOOL ================================
# =========================================================
class DocumentIngestTool:
    def __init__(self):
        self.connector = Neo4jConnector()

    def ingest_document(self, file_path: str, doc_type: str = "pdf", period: str = "FY2024-Q1"):
        """
        Ingest a financial document into Neo4j.
        - file_path: path to the file (simulated ingestion).
        - doc_type: pdf | excel | word.
        - period: reporting period.

        Returns: dict with summary of ingestion.
        """

        # === 1. Create Document node ===
        doc_id = f"doc_{uuid.uuid4()}"
        # connector methods are expected; if missing, connector should handle/no-op
        self.connector.create_document_node(
            doc_id=doc_id,
            name=file_path,
            doc_type=doc_type,
            period=period,
            source="local_upload"
        )

        # === 2. Simulated parse of Statements ===
        statements = [
            {"id": f"stmt_{uuid.uuid4()}", "type": "IncomeStatement"},
            {"id": f"stmt_{uuid.uuid4()}", "type": "BalanceSheet"}
        ]

        for stmt in statements:
            self.connector.create_statement_node(
                stmt_id=stmt["id"],
                stmt_type=stmt["type"],
                period=period,
                doc_id=doc_id
            )

        # === 3. Simulated LineItems ===
        lineitems = [
            {"name": "Revenue", "value": 1000000, "currency": "USD"},
            {"name": "Expenses", "value": 700000, "currency": "USD"},
            {"name": "NetIncome", "value": 300000, "currency": "USD"}
        ]

        for li in lineitems:
            li_id = f"li_{uuid.uuid4()}"
            self.connector.create_lineitem_node(
                li_id=li_id,
                name=li["name"],
                value=li["value"],
                currency=li["currency"],
                stmt_id=statements[0]["id"]  # Attach to first statement
            )

        return {
            "document": doc_id,
            "statements": [s["id"] for s in statements],
            "lineitems": lineitems
        }