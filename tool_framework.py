"""
Base Tool Agent Framework for Agentic Choreography Engine

This module provides the foundation for integrating diverse tools
into the agent orchestration system.
"""

import os
import importlib
import inspect
from typing import Dict, List, Any, Optional
from abc import ABC, abstractmethod
from datetime import datetime
import logging
from dataclasses import dataclass

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class ToolResult:
    """Standardized result format for all tool executions"""
    tool_name: str
    execution_id: str
    success: bool
    output: Any
    error_message: Optional[str] = None
    execution_time: float = 0.0
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}

@dataclass
class ToolCapabilities:
    """Defines what a tool can do"""
    name: str
    description: str
    input_types: List[str]
    output_types: List[str]
    capabilities: List[str]
    reliability_score: float = 0.0
    avg_execution_time: float = 0.0
    version: str = "1.0.0"

class BaseToolAgent(ABC):
    """Base class for all tool agents in the system"""

    def __init__(self):
        self.execution_count = 0
        self.success_count = 0
        self.total_execution_time = 0.0

    @property
    def name(self) -> str:
        """Unique name identifier for the tool"""
        return self.__class__.__name__.replace("ToolAgent", "").lower()

    @property
    def description(self) -> str:
        """Human-readable description of the tool"""
        return "Generic tool agent"

    @property
    def capabilities(self) -> ToolCapabilities:
        """Tool capabilities and metadata"""
        return ToolCapabilities(
            name=self.name,
            description=self.description,
            input_types=["generic"],
            output_types=["generic"],
            capabilities=["basic_execution"]
        )

    def validate_input(self, task: Dict[str, Any]) -> bool:
        """Validate task parameters before execution"""
        required_fields = getattr(self, 'required_fields', [])
        return all(field in task for field in required_fields)

    @abstractmethod
    def execute(self, task: Dict[str, Any]) -> ToolResult:
        """Execute the tool with given task parameters"""
        pass

    def format_output(self, result: Any) -> Dict[str, Any]:
        """Format tool output for next agent in chain"""
        return {
            "tool_name": self.name,
            "result": result,
            "timestamp": datetime.now().isoformat()
        }

    def update_metrics(self, execution_time: float, success: bool):
        """Update internal performance metrics"""
        self.execution_count += 1
        self.total_execution_time += execution_time
        if success:
            self.success_count += 1

    def get_performance_stats(self) -> Dict[str, Any]:
        """Get current performance statistics"""
        if self.execution_count == 0:
            return {"success_rate": 0.0, "avg_time": 0.0}

        return {
            "success_rate": self.success_count / self.execution_count,
            "avg_execution_time": self.total_execution_time / self.execution_count,
            "total_executions": self.execution_count
        }

    def __str__(self) -> str:
        return f"{self.name}: {self.description}"


class ToolExecutionError(Exception):
    """Exception raised when tool execution fails"""
    pass


class ToolRegistry:
    """Registry for managing and discovering tool agents"""

    def __init__(self, plugin_directory: str = "tools"):
        self.tools: Dict[str, BaseToolAgent] = {}
        self.plugin_directory = plugin_directory
        self.load_plugins()

    def load_plugins(self):
        """Discover and load tool plugins from directory"""
        if not os.path.exists(self.plugin_directory):
            logger.warning(f"Plugin directory {self.plugin_directory} does not exist")
            return

        for filename in os.listdir(self.plugin_directory):
            if filename.endswith("_tool.py"):
                try:
                    self._load_tool_plugin(filename)
                except Exception as e:
                    logger.error(f"Failed to load plugin {filename}: {e}")

    def _load_tool_plugin(self, plugin_file: str):
        """Load a single tool plugin"""
        module_name = plugin_file[:-3]  # Remove .py extension
        module_path = f"{self.plugin_directory}.{module_name}"

        try:
            module = importlib.import_module(module_path)
            # Find all classes that inherit from BaseToolAgent
            for name, obj in inspect.getmembers(module):
                if (inspect.isclass(obj) and
                    issubclass(obj, BaseToolAgent) and
                    obj != BaseToolAgent):
                    tool_instance = obj()
                    self.register_tool(tool_instance)
                    logger.info(f"Loaded tool: {tool_instance.name}")

        except Exception as e:
            logger.error(f"Error loading plugin {plugin_file}: {e}")

    def register_tool(self, tool: BaseToolAgent):
        """Register a tool instance"""
        self.tools[tool.name] = tool

    def get_tool(self, name: str) -> Optional[BaseToolAgent]:
        """Get a tool by name"""
        return self.tools.get(name)

    def find_tools_by_capability(self, capability: str) -> List[BaseToolAgent]:
        """Find tools that have a specific capability"""
        return [tool for tool in self.tools.values()
                if capability in tool.capabilities.capabilities]

    def find_tools_by_input_type(self, input_type: str) -> List[BaseToolAgent]:
        """Find tools that can handle specific input types"""
        return [tool for tool in self.tools.values()
                if input_type in tool.capabilities.input_types]

    def get_all_tools(self) -> List[BaseToolAgent]:
        """Get all registered tools"""
        return list(self.tools.values())

    def get_tool_metadata(self) -> Dict[str, Dict[str, Any]]:
        """Get metadata for all tools"""
        return {
            name: {
                "description": tool.description,
                "capabilities": tool.capabilities.capabilities,
                "input_types": tool.capabilities.input_types,
                "output_types": tool.capabilities.output_types,
                "performance": tool.get_performance_stats()
            }
            for name, tool in self.tools.items()
        }
