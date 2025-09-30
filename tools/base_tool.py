"""
base_tool.py

Defines the abstract base class for all tools (API, RPA, etc.)
Each tool must implement:
- name
- execute(input_data)
"""

from abc import ABC, abstractmethod

class BaseTool(ABC):
    def __init__(self, name):
        self.name = name

    @abstractmethod
    def execute(self, input_data: dict) -> dict:
        """
        Execute the tool on input data.
        Must return a dict containing:
        - success (bool)
        - output (any)
        - error (optional string)
        """
        pass
