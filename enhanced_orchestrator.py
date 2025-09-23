"""
Enhanced Orchestrator for Tool-Integrated Agentic Choreography Engine

This module extends the base choreography system to work with diverse tools
through the tool agent framework.
"""

import time
import uuid
from typing import Dict, List, Any, Optional
from datetime import datetime
import logging
from neo4j_connector import Neo4jConnector
from tool_framework import (
    BaseToolAgent, ToolRegistry, ToolResult,
    ToolCapabilities, ToolExecutionError
)

logger = logging.getLogger(__name__)

class EnhancedOrchestrator:
    """Enhanced orchestrator that integrates tools with the existing agent system"""

    def __init__(self, neo4j_connector: Neo4jConnector, faiss_service_url: str):
        self.neo4j = neo4j_connector
        self.faiss_url = faiss_service_url
        self.tool_registry = ToolRegistry()
        self.execution_history = []

    def orchestrate_with_tools(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Main orchestration method that integrates tools with agents"""

        execution_id = str(uuid.uuid4())
        start_time = time.time()

        try:
            logger.info(f"Starting enhanced orchestration for task: {task.get('description', 'Unknown')}")

            # Step 1: Find relevant tools using FAISS
            relevant_tools = self._find_relevant_tools(task)
            logger.info(f"Found {len(relevant_tools)} relevant tools")

            # Step 2: Create execution plan
            execution_plan = self._create_execution_plan(task, relevant_tools)
            logger.info(f"Created execution plan with {len(execution_plan)} steps")

            # Step 3: Execute plan
            results = self._execute_plan(execution_plan, task, execution_id)

            # Step 4: Store execution in Neo4j for learning
            self._store_execution_trace(execution_id, task, results, start_time)

            execution_time = time.time() - start_time

            return {
                "execution_id": execution_id,
                "success": all(result.success for result in results),
                "results": results,
                "execution_time": execution_time,
                "tools_used": len(relevant_tools)
            }

        except Exception as e:
            logger.error(f"Orchestration failed: {e}")
            execution_time = time.time() - start_time
            return {
                "execution_id": execution_id,
                "success": False,
                "results": [],
                "execution_time": execution_time,
                "error": str(e)
            }

    def _find_relevant_tools(self, task: Dict[str, Any]) -> List[BaseToolAgent]:
        """Find tools relevant to the given task using FAISS"""

        # First, try to find tools using FAISS vector similarity
        try:
            import requests

            faiss_response = requests.post(
                self.faiss_url,
                json={"query": task.get("description", "")},
                timeout=5
            )

            if faiss_response.status_code == 200:
                similar_tools = faiss_response.json()
                # Map FAISS results to tool registry
                relevant_tools = []
                for tool_result in similar_tools:
                    tool = self.tool_registry.get_tool(tool_result["name"])
                    if tool:
                        relevant_tools.append(tool)
                return relevant_tools

        except Exception as e:
            logger.warning(f"FAISS tool discovery failed: {e}")

        # Fallback: Find tools by capability matching
        task_type = self._infer_task_type(task)
        relevant_tools = self.tool_registry.find_tools_by_capability(task_type)

        # Additional filtering by input type
        if "input_type" in task:
            relevant_tools = [
                tool for tool in relevant_tools
                if task["input_type"] in tool.capabilities.input_types
            ]

        return relevant_tools

    def _infer_task_type(self, task: Dict[str, Any]) -> str:
        """Infer the type of task based on content"""
        description = task.get("description", "").lower()

        # Simple keyword-based inference
        if any(keyword in description for keyword in ["database", "sql", "query", "data"]):
            return "data_processing"
        elif any(keyword in description for keyword in ["api", "web", "http", "rest"]):
            return "api_integration"
        elif any(keyword in description for keyword in ["file", "read", "write", "storage"]):
            return "file_operations"
        elif any(keyword in description for keyword in ["search", "find", "lookup"]):
            return "search"
        else:
            return "general"

    def _create_execution_plan(self, task: Dict[str, Any], tools: List[BaseToolAgent]) -> List[Dict[str, Any]]:
        """Create an execution plan for the task"""

        plan = []

        # If we have relevant tools, include them in the plan
        if tools:
            for tool in tools:
                plan.append({
                    "type": "tool",
                    "tool_name": tool.name,
                    "description": f"Execute {tool.description}",
                    "estimated_time": tool.capabilities.avg_execution_time
                })

        # Add final agent step if needed
        plan.append({
            "type": "agent",
            "agent_type": "synthesis",
            "description": "Synthesize results from all tools"
        })

        return plan

    def _execute_plan(self, plan: List[Dict[str, Any]], task: Dict[str, Any], execution_id: str) -> List[ToolResult]:
        """Execute the plan and collect results"""

        results = []

        for step in plan:
            try:
                if step["type"] == "tool":
                    result = self._execute_tool_step(step, task, execution_id)
                else:
                    result = self._execute_agent_step(step, task, execution_id)

                results.append(result)
                logger.info(f"Executed step: {step['description']} - Success: {result.success}")

                # Break on first failure if configured
                if not result.success and task.get("fail_fast", False):
                    break

            except Exception as e:
                logger.error(f"Step failed: {step['description']} - {e}")
                results.append(ToolResult(
                    tool_name=step.get("tool_name", "unknown"),
                    execution_id=execution_id,
                    success=False,
                    output=None,
                    error_message=str(e)
                ))

        return results

    def _execute_tool_step(self, step: Dict[str, Any], task: Dict[str, Any], execution_id: str) -> ToolResult:
        """Execute a single tool step"""

        tool_name = step["tool_name"]
        tool = self.tool_registry.get_tool(tool_name)

        if not tool:
            raise ToolExecutionError(f"Tool {tool_name} not found")

        # Validate input
        if not tool.validate_input(task):
            raise ToolExecutionError(f"Invalid input for tool {tool_name}")

        # Execute tool
        start_time = time.time()
        try:
            result = tool.execute(task)
            execution_time = time.time() - start_time

            # Update tool metrics
            tool.update_metrics(execution_time, result.success)

            return result

        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(f"Tool execution failed: {e}")

            return ToolResult(
                tool_name=tool_name,
                execution_id=execution_id,
                success=False,
                output=None,
                error_message=str(e),
                execution_time=execution_time
            )

    def _execute_agent_step(self, step: Dict[str, Any], task: Dict[str, Any], execution_id: str) -> ToolResult:
        """Execute a standard agent step (placeholder for now)"""

        # This would integrate with the existing agent system
        # For now, return a placeholder result
        return ToolResult(
            tool_name=step.get("agent_type", "agent"),
            execution_id=execution_id,
            success=True,
            output={"message": "Agent execution completed"},
            execution_time=0.1
        )

    def _store_execution_trace(self, execution_id: str, task: Dict[str, Any], results: List[ToolResult], start_time: float):
        """Store execution trace in Neo4j for learning"""

        try:
            # Create execution node
            execution_query = """
            MERGE (e:Execution {id: $execution_id})
            SET e.description = $task_description,
                e.timestamp = $timestamp,
                e.success = $success,
                e.execution_time = $execution_time
            """

            self.neo4j.query(execution_query, {
                "execution_id": execution_id,
                "task_description": task.get("description", ""),
                "timestamp": datetime.now().isoformat(),
                "success": all(r.success for r in results),
                "execution_time": time.time() - start_time
            })

            # Create tool execution nodes and relationships
            for result in results:
                tool_query = """
                MATCH (e:Execution {id: $execution_id})
                MERGE (t:ToolExecution {id: $tool_execution_id})
                SET t.tool_name = $tool_name,
                    t.success = $success,
                    t.execution_time = $execution_time
                MERGE (e)-[:USED_TOOL]->(t)
                """

                self.neo4j.query(tool_query, {
                    "execution_id": execution_id,
                    "tool_execution_id": f"{execution_id}_{result.tool_name}",
                    "tool_name": result.tool_name,
                    "success": result.success,
                    "execution_time": result.execution_time
                })

        except Exception as e:
            logger.error(f"Failed to store execution trace: {e}")

    def get_system_status(self) -> Dict[str, Any]:
        """Get current system status and tool information"""

        return {
            "total_tools": len(self.tool_registry.get_all_tools()),
            "tool_metadata": self.tool_registry.get_tool_metadata(),
            "execution_history_count": len(self.execution_history)
        }

    def add_tool(self, tool: BaseToolAgent):
        """Add a new tool to the registry"""
        self.tool_registry.register_tool(tool)
        logger.info(f"Added new tool: {tool.name}")
