"""
Multi-Agent System for MCP Tool Calling
Autonomous decision-making system that adapts to any task
"""

from .base_agent import BaseAgent
from .strategy_agent import StrategyAgent
from .selector_agent import ToolSelectorAgent
from .executor_agent import ExecutorAgent
from .context_manager import SharedContextManager
from .autonomous_coordinator import AutonomousCoordinator

__all__ = [
    'BaseAgent',
    'StrategyAgent',
    'ToolSelectorAgent',
    'ExecutorAgent',
    'SharedContextManager',
    'AutonomousCoordinator'
]
