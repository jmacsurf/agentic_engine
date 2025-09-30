from .base_tool import BaseTool
from typing import Any

class RPATool(BaseTool):
    """Example RPA tool implementation (lightweight simulation).

    This file is intentionally minimal and does not import heavy or network
    dependencies so importing the package is safe during discovery.
    """
    name = "rpa_tool"

    def execute(self, action: str, payload: dict | None = None) -> dict:
        payload = payload or {}
        # Simulate an RPA action - in real code this would drive a browser or RPA engine
        result = {
            "tool": self.name,
            "action": action,
            "payload": payload,
            "status": "simulated",
            "timestamp": __import__("datetime").datetime.utcnow().isoformat() + "Z"
        }
        return result

# Export a default instance for simple discovery
TOOL = RPATool()
