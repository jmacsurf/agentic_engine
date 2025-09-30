"""
tool_manager.py

Dynamic tool manager:
- Loads tool definitions from tools_config.yaml
- Supports API and RPA types (extensible)
- Executes tools uniformly
"""

import os
import yaml
from .api_tool import APITool
from .rpa_tool import RPATool

class ToolManager:
    def __init__(self, config_file=None):
        """
        Initialize ToolManager.
        Loads tools from YAML config file.
        """
        self.config_file = config_file or os.path.join(os.path.dirname(__file__), "tools_config.yaml")
        self.tools = {}
        self.load_tools()

    # =====================================================
    # === LOAD TOOLS FROM CONFIG ==========================
    # =====================================================
    def load_tools(self):
        """Load tool definitions from YAML config and instantiate them."""
        if not os.path.exists(self.config_file):
            raise FileNotFoundError(f"Config file not found: {self.config_file}")

        with open(self.config_file, "r") as f:
            config = yaml.safe_load(f)

        for tool_cfg in config.get("tools", []):
            name = tool_cfg["name"]
            ttype = tool_cfg["type"]
            params = tool_cfg.get("params", {})

            if ttype == "api":
                self.tools[name] = APITool(endpoint=params.get("endpoint"))
            elif ttype == "rpa":
                self.tools[name] = RPATool()
            else:
                print(f"⚠️ Unknown tool type: {ttype} (skipping {name})")

        print(f"✅ Loaded tools: {list(self.tools.keys())}")

    # =====================================================
    # === TOOL INTERFACE ==================================
    # =====================================================
    def list_tools(self):
        """Return list of available tool names."""
        return list(self.tools.keys())

    def execute(self, tool_name, input_data):
        """Execute a registered tool by name."""
        tool = self.tools.get(tool_name)
        if not tool:
            return {"success": False, "error": f"Tool {tool_name} not found"}
        return tool.execute(input_data)
