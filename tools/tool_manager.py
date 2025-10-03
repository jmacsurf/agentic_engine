"""
tool_manager.py

Dynamic tool manager:
- Loads tool definitions from tools_config.yaml
- Supports API and RPA types (extensible)
- Executes tools uniformly
"""

from __future__ import annotations
import os
import logging
import json
import yaml
from .api_tool import APITool
from .rpa_tool import RPATool

class ToolManager:
    def __init__(self, config_path: str | None = None):
        """
        Initialize ToolManager.
        Loads tools from YAML config file.
        """
        self.tools = {}
        self.config_path = config_path or os.path.join(os.path.dirname(__file__), "tools.yaml")
        self.load_tools()

    # =====================================================
    # === LOAD TOOLS FROM CONFIG ==========================
    # =====================================================
    def load_tools(self):
        """Load tools from config; be robust to different formats (list, dict, JSON string)."""
        try:
            if not os.path.exists(self.config_path):
                logging.info("No tools config found at %s, continuing with empty registry", self.config_path)
                return

            with open(self.config_path, "r") as f:
                raw = f.read()

            # Try YAML/JSON parse
            try:
                tools_cfg = yaml.safe_load(raw)
            except Exception:
                try:
                    tools_cfg = json.loads(raw)
                except Exception:
                    tools_cfg = raw.strip()

            # Normalize into a list of dicts
            if isinstance(tools_cfg, dict):
                tools_list = [tools_cfg]
            elif isinstance(tools_cfg, list):
                tools_list = tools_cfg
            elif isinstance(tools_cfg, str):
                # single name string -> wrap into minimal config
                tools_list = [{"name": tools_cfg}]
            else:
                logging.warning("Unexpected tools config type: %s", type(tools_cfg))
                return

            for tool_cfg in tools_list:
                if not isinstance(tool_cfg, dict):
                    logging.warning("Skipping invalid tool entry (not a dict): %r", tool_cfg)
                    continue
                name = tool_cfg.get("name")
                if not name:
                    logging.warning("Skipping tool with no name: %r", tool_cfg)
                    continue
                # register minimal placeholder if no class available
                try:
                    # assume a factory or dynamic loader exists; otherwise register a placeholder
                    self.tools[name] = {
                        "config": tool_cfg,
                        "instance": None
                    }
                except Exception as e:
                    logging.warning("Failed to register tool %s: %s", name, e)

            logging.info("Loaded %d tools from %s", len(self.tools), self.config_path)

        except Exception as e:
            logging.exception("Failed to load tools config: %s", e)

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
