"""
Multi-Agent Coordinator
Orchestrates the three-tier agent system
"""

from typing import Dict, Any, Optional
from rich.console import Console
from .master_agent import MasterAgent
from .selector_agent import ToolSelectorAgent
from .executor_agent import ExecutorAgent
from .context_manager import SharedContextManager
import ollama


class MultiAgentCoordinator:
    """
    Coordinates the three-tier agent system:
    1. Master Agent: Planning
    2. Tool Selector Agent: Tool filtering
    3. Executor Agent: Execution
    """
    
    def __init__(
        self,
        model: str,
        console: Console,
        tool_manager,
        client
    ):
        self.model = model
        self.console = console
        self.tool_manager = tool_manager
        self.client = client  # MCPClient reference for tool calling
        
        # Initialize shared context
        self.context_manager = SharedContextManager()
        
        # Initialize agents
        self.master = MasterAgent(model, console, self.context_manager)
        self.selector = ToolSelectorAgent(model, console, self.context_manager, tool_manager)
        self.executor = ExecutorAgent(model, console, self.context_manager, client)
        
        self.console.print("[green]✓ Multi-Agent system initialized[/green]")
        self.console.print(f"[cyan]  - Master Agent: {model}[/cyan]")
        self.console.print(f"[cyan]  - Tool Selector: {model}[/cyan]")
        self.console.print(f"[cyan]  - Executor: {model}[/cyan]")
        
    async def process_query(self, query: str) -> str:
        """
        Process a user query through the multi-agent system
        
        Workflow:
        1. Master creates task plan
        2. For each step:
           a. Selector filters relevant tools
           b. Executor runs tools and summarizes
        3. Master aggregates final report
        """
        self.console.print(f"\n[bold cyan]{'='*70}[/bold cyan]")
        self.console.print(f"[bold cyan]Multi-Agent System Processing Query[/bold cyan]")
        self.console.print(f"[bold cyan]{'='*70}[/bold cyan]\n")
        
        # Stage 1: Planning
        self.console.print("[bold yellow]Stage 1: Task Planning[/bold yellow]")
        plan = await self.master.process({
            "mode": "plan",
            "query": query
        })
        
        steps = plan.get("steps", [])
        self.console.print(f"[green]✓ Created plan with {len(steps)} steps[/green]\n")
        
        # Display plan
        for step in steps:
            self.console.print(f"  Step {step['step_id']}: {step['description']}")
            self.console.print(f"    Keywords: {', '.join(step.get('tool_keywords', []))}")
        
        self.console.print("")
        
        # Stage 2: Execute each step
        for step in steps:
            step_id = step["step_id"]
            description = step["description"]
            keywords = step.get("tool_keywords", [])
            
            self.console.print(f"\n[bold yellow]Stage 2.{step_id}: Processing Step {step_id}[/bold yellow]")
            self.console.print(f"Task: {description}")
            
            # 2a: Tool Selection
            self.console.print(f"\n[cyan]→ Tool Selector Agent[/cyan]")
            selection_result = await self.selector.process({
                "step_id": step_id,
                "description": description,
                "keywords": keywords
            })
            
            # Get tool objects from the message
            messages = self.context_manager.get_messages_for_agent("ExecutorAgent")
            latest_message = messages[-1] if messages else None
            
            if not latest_message:
                self.console.print("[red]Error: No tool selection message found[/red]")
                continue
                
            tool_objects = latest_message.content.get("tool_objects", [])
            
            if not tool_objects:
                self.console.print("[yellow]⚠ No tools selected, skipping execution[/yellow]")
                continue
                
            # 2b: Tool Execution
            self.console.print(f"\n[cyan]→ Executor Agent[/cyan]")
            execution_result = await self.executor.process({
                "step_id": step_id,
                "description": description,
                "target": self._extract_target_from_query(query),
                "tool_objects": tool_objects
            })
            
            # Display summary
            summary = execution_result.get("summary", "")
            self.console.print(f"\n[green]Summary:[/green]")
            self.console.print(f"  {summary[:200]}...")
            
        # Stage 3: Aggregation
        self.console.print(f"\n[bold yellow]Stage 3: Aggregating Results[/bold yellow]")
        final_result = await self.master.process({
            "mode": "aggregate"
        })
        
        final_report = final_result.get("final_report", "")
        
        self.console.print(f"\n[bold cyan]{'='*70}[/bold cyan]")
        self.console.print(f"[bold green]Final Report[/bold green]")
        self.console.print(f"[bold cyan]{'='*70}[/bold cyan]\n")
        
        return final_report
        
    def _extract_target_from_query(self, query: str) -> Optional[str]:
        """
        Extract target IP/hostname from query
        Simple regex-based extraction
        """
        import re
        
        # Look for IP addresses
        ip_pattern = r'\b(?:\d{1,3}\.){3}\d{1,3}\b'
        match = re.search(ip_pattern, query)
        if match:
            return match.group(0)
            
        # Look for common hostname patterns
        hostname_pattern = r'\b(?:www\.)?[\w-]+\.[\w.-]+\b'
        match = re.search(hostname_pattern, query)
        if match:
            return match.group(0)
            
        return None
        
    def get_context_summary(self) -> Dict[str, Any]:
        """Get current context summary for debugging"""
        return self.context_manager.get_context_summary()
        
    def get_progress_report(self) -> str:
        """Get progress report"""
        return self.context_manager.get_progress_report()
