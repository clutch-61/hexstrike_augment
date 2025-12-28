"""
Shared Context Manager
Manages inter-agent communication and state sharing
"""

from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class TaskStep:
    """Represents a single step in a multi-step task"""
    step_id: int
    description: str
    status: str = "pending"  # pending, in_progress, completed, failed
    assigned_tools: List[str] = field(default_factory=list)
    results: Dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    

@dataclass
class AgentMessage:
    """Message passed between agents"""
    from_agent: str
    to_agent: str
    message_type: str  # task_plan, tool_selection, execution_result, analysis
    content: Dict[str, Any]
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


class SharedContextManager:
    """
    Manages shared state between agents to minimize token duplication
    """
    
    def __init__(self):
        self.original_query: str = ""
        self.task_steps: List[TaskStep] = []
        self.messages: List[AgentMessage] = []
        self.global_context: Dict[str, Any] = {}
        self.execution_summary: List[str] = []
        
    def set_query(self, query: str):
        """Store the original user query"""
        self.original_query = query
        
    def add_task_step(self, step: TaskStep):
        """Add a new task step to the plan"""
        self.task_steps.append(step)
        
    def update_step_status(self, step_id: int, status: str, results: Optional[Dict] = None):
        """Update the status of a specific step"""
        for step in self.task_steps:
            if step.step_id == step_id:
                step.status = status
                if results:
                    step.results = results
                break
                
    def get_step(self, step_id: int) -> Optional[TaskStep]:
        """Retrieve a specific task step"""
        for step in self.task_steps:
            if step.step_id == step_id:
                return step
        return None
        
    def get_pending_steps(self) -> List[TaskStep]:
        """Get all steps that are not yet completed"""
        return [step for step in self.task_steps if step.status != "completed"]
        
    def add_message(self, message: AgentMessage):
        """Add an inter-agent message"""
        self.messages.append(message)
        
    def get_messages_for_agent(self, agent_name: str) -> List[AgentMessage]:
        """Get all messages directed to a specific agent"""
        return [msg for msg in self.messages if msg.to_agent == agent_name]
        
    def add_execution_summary(self, summary: str):
        """Add a summarized execution result (for token efficiency)"""
        self.execution_summary.append(summary)
        
    def get_context_summary(self) -> Dict[str, Any]:
        """
        Get a token-efficient summary of the current context
        Returns only essential information to minimize token usage
        """
        return {
            "query": self.original_query,
            "total_steps": len(self.task_steps),
            "completed_steps": sum(1 for step in self.task_steps if step.status == "completed"),
            "current_step": next((step for step in self.task_steps if step.status == "in_progress"), None),
            "recent_summaries": self.execution_summary[-10:],  # Keep last 10 summaries for better context
            "global_context": self.global_context
        }
        
    def set_global_context(self, key: str, value: Any):
        """Store global context information accessible by all agents"""
        self.global_context[key] = value
        
    def get_global_context(self, key: str, default=None) -> Any:
        """Retrieve global context information"""
        return self.global_context.get(key, default)
        
    def clear_old_messages(self, keep_last_n: int = 5):
        """Clear old messages to reduce memory/token usage"""
        if len(self.messages) > keep_last_n:
            self.messages = self.messages[-keep_last_n:]
            
    def get_progress_report(self) -> str:
        """Generate a concise progress report"""
        completed = sum(1 for step in self.task_steps if step.status == "completed")
        total = len(self.task_steps)
        
        report = f"Task Progress: {completed}/{total} steps completed\n"
        for step in self.task_steps:
            status_icon = "✓" if step.status == "completed" else "○"
            report += f"{status_icon} Step {step.step_id}: {step.description} ({step.status})\n"
        
        return report
