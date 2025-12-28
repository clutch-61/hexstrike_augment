"""
Master Agent
Coordinates the overall task execution and delegates to specialized agents
"""

from typing import Dict, Any, List
from .base_agent import BaseAgent
from .context_manager import TaskStep, AgentMessage


class MasterAgent(BaseAgent):
    """
    Master Agent: Task Planning and Coordination
    - Analyzes user query
    - Breaks down into steps
    - Coordinates execution flow
    - Aggregates final results
    """
    
    def __init__(self, model: str, console, context_manager):
        system_prompt = """You are a Master Planning Agent for penetration testing tasks.

Your role:
1. Analyze user queries and break them into sequential steps
2. Identify which tools are needed for each step
3. Coordinate execution flow
4. Aggregate results into a final report

Output Format (JSON):
{
    "steps": [
        {
            "step_id": 1,
            "description": "Scan target for open ports",
            "tool_keywords": ["nmap", "port", "scan"],
            "depends_on": []
        },
        {
            "step_id": 2,
            "description": "Detect vulnerabilities on discovered services",
            "tool_keywords": ["nuclei", "vulnerability", "detect"],
            "depends_on": [1]
        }
    ],
    "reasoning": "Brief explanation of the plan"
}

Keep plans concise. Maximum 5 steps for complex tasks."""

        super().__init__(
            name="MasterAgent",
            model=model,
            console=console,
            context_manager=context_manager,
            system_prompt=system_prompt
        )
        
    async def process(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Main processing logic for Master Agent
        
        Input: {"query": "user query", "mode": "plan" or "aggregate"}
        Output: {"steps": [...]} or {"final_report": "..."}
        """
        mode = input_data.get("mode", "plan")
        
        if mode == "plan":
            return await self._create_task_plan(input_data["query"])
        elif mode == "aggregate":
            return await self._aggregate_results()
        else:
            raise ValueError(f"Unknown mode: {mode}")
            
    async def _create_task_plan(self, query: str) -> Dict[str, Any]:
        """
        Analyze query and create task plan
        Returns plan with steps and tool keywords
        """
        self.log(f"Creating task plan for query: {query[:100]}...")
        
        # Store query in shared context
        self.context_manager.set_query(query)
        
        # Ask model to break down the task
        prompt = f"""Analyze this penetration testing query and create a step-by-step plan:

Query: {query}

Create a JSON plan with steps. Each step should have:
- step_id: sequential number
- description: what to do
- tool_keywords: 2-3 keywords to find relevant tools
- depends_on: list of step IDs that must complete first

Output ONLY valid JSON, no other text."""

        try:
            # Use smaller token budget for planning
            response = await self.call_model(prompt, max_tokens=3000)
            
            # Parse JSON response
            import json
            # Extract JSON from response (handle markdown code blocks)
            json_start = response.find('{')
            json_end = response.rfind('}') + 1
            if json_start >= 0 and json_end > json_start:
                json_str = response[json_start:json_end]
                plan = json.loads(json_str)
            else:
                raise ValueError("No valid JSON found in response")
            
            # Store steps in context manager
            for step_data in plan.get("steps", []):
                step = TaskStep(
                    step_id=step_data["step_id"],
                    description=step_data["description"],
                    status="pending"
                )
                self.context_manager.add_task_step(step)
                
            self.log(f"✓ Plan created with {len(plan['steps'])} steps", "success")
            
            # Send message to Tool Selector Agent
            message = AgentMessage(
                from_agent=self.name,
                to_agent="ToolSelectorAgent",
                message_type="task_plan",
                content={
                    "steps": plan["steps"],
                    "query": query
                }
            )
            self.context_manager.add_message(message)
            
            return plan
            
        except Exception as e:
            self.log(f"Error creating plan: {e}", "error")
            # Fallback: create simple single-step plan
            fallback_plan = {
                "steps": [{
                    "step_id": 1,
                    "description": query,
                    "tool_keywords": ["scan", "detect", "exploit"],
                    "depends_on": []
                }],
                "reasoning": "Fallback single-step plan due to parsing error"
            }
            
            step = TaskStep(step_id=1, description=query, status="pending")
            self.context_manager.add_task_step(step)
            
            return fallback_plan
            
    async def _aggregate_results(self) -> Dict[str, Any]:
        """
        Aggregate results from all completed steps into final report
        """
        self.log("Aggregating results into final report...")
        
        # Get context summary
        summary = self.context_manager.get_context_summary()
        
        # Build report from execution summaries
        report_prompt = f"""Create a final report for this penetration testing task:

Original Query: {summary['query']}

Completed Steps: {summary['completed_steps']}/{summary['total_steps']}

Execution Results:
{chr(10).join(summary['recent_summaries'])}

Provide a concise summary with:
1. What was accomplished
2. Key findings
3. Recommendations (if applicable)

Keep it brief and actionable."""

        try:
            report = await self.call_model(report_prompt, max_tokens=3000)
            
            self.log("✓ Final report generated", "success")
            
            return {
                "final_report": report,
                "stats": {
                    "total_steps": summary['total_steps'],
                    "completed_steps": summary['completed_steps']
                }
            }
            
        except Exception as e:
            self.log(f"Error generating report: {e}", "error")
            # Fallback report
            return {
                "final_report": f"Task completed: {summary['completed_steps']}/{summary['total_steps']} steps finished.",
                "stats": {
                    "total_steps": summary['total_steps'],
                    "completed_steps": summary['completed_steps']
                }
            }
