"""
test_async_run.py

Quick test harness for the EnhancedOrchestrator (async).
Runs a demo workflow and prints execution logs.
"""
import sys
import os
import asyncio

# ensure project root is on sys.path so imports like "import enhanced_orchestrator" work
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

# import the module from the project root
from enhanced_orchestrator import EnhancedOrchestrator


async def main():
    orch = EnhancedOrchestrator()
    await orch.run_workflow("workflow_demo")


if __name__ == "__main__":
    asyncio.run(main())
