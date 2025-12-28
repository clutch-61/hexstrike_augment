"""
Strategy Agent - Autonomous Decision Making
Continuously analyzes context and decides next actions
"""

from typing import Dict, Any, Optional
from .base_agent import BaseAgent
import json


class StrategyAgent(BaseAgent):
    """
    Strategy Agent: Autonomous Task Coordination
    
    Operates in a continuous decision loop:
    1. Analyze current context (query, results so far, gaps)
    2. Decide: Should we continue? What's next? Are we done?
    3. Generate specific sub-task if continuing
    4. Evaluate results when they come back
    5. Repeat until objectives met
    
    This enables true autonomous multi-agent systems that can:
    - Handle vague queries ("scan this target for vulnerabilities")
    - Adapt based on discoveries
    - Make intelligent next-step decisions
    - Know when to stop
    """
    
    def __init__(self, model: str, console, context_manager):
        system_prompt = """You are a Strategy Agent for autonomous penetration testing.

Your Core Mission:
Analyze the situation, decide what to do next, execute, evaluate, repeat.

Decision Process:
1. CONTEXT: What do we know? What's the goal? What have we tried?
2. ANALYZE: What information is missing? What should we do next?
3. DECIDE: Continue with new task OR Finish if goal achieved
4. GENERATE: If continuing, create specific actionable sub-task

Output Format (JSON only):

For CONTINUE (when more work needed):
{
    "decision": "continue",
    "reasoning": "Why this next step is needed",
    "current_progress": "Brief summary of what we know",
    "next_task": {
        "description": "Specific action (e.g., 'Use nmap to scan 10.81.0.64:8209')",
        "tool_keywords": ["nmap", "port", "scan"],
        "expected_outcome": "What we hope to learn",
        "parameters": {
            "target": "10.81.0.64:8209"
        }
    }
}

For FINISH (when objective achieved or impossible):
{
    "decision": "finish",
    "reasoning": "Why we're stopping",
    "final_summary": "Complete summary of findings",
    "recommendations": "Next steps for the user"
}

Critical Rules:
- Output ONLY valid JSON, no extra text
- Be specific in task descriptions
- Include relevant parameters (IPs, ports, CVEs)
- Make autonomous decisions based on results
- Know when you've answered the user's question

Think autonomously. Act purposefully. Stop when done."""

        super().__init__(
            name="StrategyAgent",
            model=model,
            console=console,
            context_manager=context_manager,
            system_prompt=system_prompt
        )
        
    async def process(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Required by BaseAgent abstract class
        Delegates to specific methods based on input
        """
        mode = input_data.get("mode", "decide")
        
        if mode == "decide":
            return await self.decide_next_action(
                user_query=input_data["user_query"],
                execution_history=input_data.get("execution_history", []),
                iteration=input_data.get("iteration", 1)
            )
        elif mode == "report":
            report = await self.generate_final_report(
                user_query=input_data["user_query"],
                execution_history=input_data.get("execution_history", [])
            )
            return {"report": report}
        else:
            return {"error": f"Unknown mode: {mode}"}
        
    async def decide_next_action(
        self,
        user_query: str,
        execution_history: list,
        iteration: int
    ) -> Dict[str, Any]:
        """
        Autonomous decision: What should we do next?
        
        Args:
            user_query: Original user request
            execution_history: List of previous tasks and results
            iteration: Current iteration number
            
        Returns:
            Decision dict with either "continue" or "finish"
        """
        # Build context summary
        history_text = ""
        if execution_history:
            for i, item in enumerate(execution_history, 1):
                history_text += f"\nTask {i}: {item.get('task', 'N/A')}\n"
                history_text += f"Result: {item.get('summary', 'N/A')[:300]}...\n"
        else:
            history_text = "No previous executions yet."
            
        # Build decision prompt
        prompt = f"""Analyze the current situation and decide the next action.

ORIGINAL USER QUERY:
{user_query}

EXECUTION HISTORY ({len(execution_history)} tasks completed):
{history_text}

CURRENT ITERATION: {iteration}
MAX ITERATIONS: 15

Your decision:
1. If the user's question is answered or goal achieved → "finish"
2. If more information needed → "continue" with specific next task
3. If stuck or max iterations reached → "finish" with current findings

Provide your decision in JSON format (ONLY JSON, no other text):"""

        try:
            response = await self.call_model(prompt, max_tokens=2000)
            
            if not response or not response.strip():
                self.log("⚠ Empty response from model", "warning")
                # Default to finish if at iteration 3+
                if iteration >= 3:
                    return {
                        "decision": "finish",
                        "reasoning": "Empty model response after multiple iterations",
                        "final_summary": "任务已完成，已执行多次工具调用。"
                    }
                else:
                    return {
                        "decision": "continue",
                        "reasoning": "Empty response, continuing analysis",
                        "next_task": {
                            "description": "Analyze previous results",
                            "tool_keywords": ["analyze"],
                            "expected_outcome": "Understanding of previous execution"
                        }
                    }
            
            # Extract JSON from response
            response = response.strip()
            
            # Try to find JSON in response
            try:
                if '{' in response and '}' in response:
                    start = response.index('{')
                    end = response.rindex('}') + 1
                    json_str = response[start:end]
                    decision = json.loads(json_str)
                else:
                    raise ValueError("No JSON found in response")
            except (ValueError, json.JSONDecodeError) as e:
                # Fallback: couldn't parse, decide based on iteration
                self.log(f"⚠ Could not parse JSON: {e}, using fallback logic", "warning")
                if iteration >= 5 or len(execution_history) >= 3:
                    decision = {
                        "decision": "finish",
                        "reasoning": "多次迭代后完成任务",
                        "final_summary": f"已完成 {len(execution_history)} 个任务。"
                    }
                else:
                    decision = {
                        "decision": "finish",
                        "reasoning": "JSON解析失败，结束任务",
                        "final_summary": "任务已完成基本分析。"
                    }
                
            self.log(f"Decision: {decision.get('decision', 'unknown')}", "info")
            
            return decision
            
        except Exception as e:
            self.log(f"Decision error: {e}", "error")
            # Fallback decision
            return {
                "decision": "finish",
                "reasoning": f"决策错误: {str(e)[:100]}",
                "final_summary": "任务因错误终止，已收集部分信息。"
            }
            
    async def generate_final_report(
        self,
        user_query: str,
        execution_history: list
    ) -> str:
        """
        Generate comprehensive final report from all executions
        """
        history_text = ""
        for i, item in enumerate(execution_history, 1):
            history_text += f"\n## Task {i}: {item.get('task', 'N/A')}\n"
            history_text += f"{item.get('summary', 'No summary available')}\n"
            
        prompt = f"""Generate a comprehensive final report.

USER QUERY:
{user_query}

EXECUTION HISTORY:
{history_text}

Create a detailed report covering:
1. Summary of actions taken
2. Key findings and discoveries
3. Security vulnerabilities identified (if any)
4. Recommendations for the user

Format in clear markdown."""

        try:
            report = await self.call_model(prompt, max_tokens=3000)
            return report.strip()
        except Exception as e:
            self.log(f"Report generation error: {e}", "error")
            return f"# Task Report\n\nCompleted {len(execution_history)} tasks.\n\n{history_text}"
