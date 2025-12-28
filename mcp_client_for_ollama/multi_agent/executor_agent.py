"""
Executor Agent
Executes selected tools and processes results
"""

from typing import Dict, Any, List
from .base_agent import BaseAgent
from .context_manager import AgentMessage
import json


class ExecutorAgent(BaseAgent):
    """
    Executor Agent: Tool Execution and Summarization
    - Receives selected tools from Selector
    - Calls the actual tools with appropriate parameters
    - Summarizes results to minimize token usage
    """
    
    def __init__(self, model: str, console, context_manager, client):
        system_prompt = """You are an Execution Agent for penetration testing tools.

Your role:
1. Analyze which tool to use based on the task
2. Determine correct parameters for the tool
3. Execute the tool via tool_calls
4. Summarize results concisely

CRITICAL: You must use tool_calls to invoke tools, not text descriptions.

After seeing tool results, create a summary:
- Key findings (2-3 points)
- Important data (IP addresses, vulnerabilities, etc.)
- Recommended next actions

Keep summaries under 200 words."""

        super().__init__(
            name="ExecutorAgent",
            model=model,
            console=console,
            context_manager=context_manager,
            system_prompt=system_prompt
        )
        self.client = client  # Reference to MCPClient for tool calling
        
    async def process(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute tools for a specific step using the client's proven tool calling mechanism
        """
        step_id = input_data["step_id"]
        description = input_data["description"]
        tool_objects = input_data["tool_objects"]
        
        self.log(f"Executing Step {step_id}: {description}")
        
        # Update step status
        self.context_manager.update_step_status(step_id, "in_progress")
        
        # Build context for execution
        context_summary = self.context_manager.get_context_summary()
        
        # Convert tool objects to MCP tool format (same as client.py)
        available_tools = []
        for tool_obj in tool_objects:
            tool_schema = {
                "type": "function",
                "function": {
                    "name": tool_obj.name,
                    "description": tool_obj.description,
                    "parameters": tool_obj.inputSchema
                }
            }
            available_tools.append(tool_schema)
            
        self.log(f"Available tools: {len(available_tools)}", "debug")
        
        # Build execution prompt
        tool_names = [t.name for t in tool_objects]
        self.log(f"Selector provided tools: {', '.join(tool_names)}", "debug")
        
        execution_prompt = f"""Execute this task step:

Task: {description}

Original Query: {context_summary['query']}
Previous Results: {', '.join(context_summary.get('recent_summaries', [])[-2:])}

The Tool Selector has pre-filtered {len(available_tools)} most relevant tools for this task:
{', '.join(tool_names)}

CRITICAL RULES:
- Choose ONLY ONE tool from the provided list that best matches the task
- Call it ONLY ONCE with correct parameters
- Do not call the same tool multiple times
- Do not call multiple different tools
- MUST choose from the tools provided by the Selector

Example for "scan port 8209 with nmap":
- If nmap_scan is in the list, call: hexstrike-ai.nmap_scan with target="10.81.0.64" ports="8209"

Example for "use curl to access /actuator/info":
- If http tools are in the list, choose the most appropriate one like httpx_probe or similar

IMPORTANT: Use tool_calls to invoke ONE tool with all required parameters."""

        # Build messages for model
        messages = [
            {
                "role": "system",
                "content": self.system_prompt
            },
            {
                "role": "user",
                "content": execution_prompt
            }
        ]
        
        # Call model ONCE to get tool selection
        tool_results = []
        summary = ""
        max_retries = 2  # Only retry on failure
        
        for attempt in range(max_retries):
            if attempt > 0:
                self.log(f"Retry attempt {attempt}/{max_retries-1}", "warning")
            
            try:
                # Use streaming like client.py does
                stream = await self.client.ollama.chat(
                    model=self.model,
                    messages=messages,
                    stream=True,
                    tools=available_tools,
                    options={
                        "num_predict": 4000,
                        "temperature": 0.3  # Lower temperature for more consistent tool selection
                    }
                )
                
                # Process streaming response
                response_text, tool_calls, _ = await self.client.streaming_manager.process_streaming_response(
                    stream,
                    thinking_mode=False,
                    show_thinking=False,
                    show_metrics=False
                )
                
                self.log(f"Model selected {len(tool_calls)} tool(s)", "debug")
                
                # If no tool calls, use model's response as summary
                if not tool_calls or len(tool_calls) == 0:
                    if response_text:
                        self.log("Model provided analysis without tools", "info")
                        summary = response_text
                        break
                    else:
                        self.log("No tool selection made", "warning")
                        if attempt < max_retries - 1:
                            continue  # Retry
                        else:
                            summary = f"Unable to select appropriate tool for: {description}"
                            break
                
                # Execute the selected tool(s) - should be just one
                execution_success = False
                for tool in tool_calls[:1]:  # Only execute the first tool call
                    tool_name = tool.function.name
                    tool_args = tool.function.arguments
                    
                    # Verify tool is in the Selector's list
                    tool_names = [t.name for t in tool_objects]
                    if tool_name not in tool_names:
                        self.log(f"⚠ Model selected '{tool_name}' which is NOT in Selector's list!", "warning")
                        self.log(f"  Available: {', '.join(tool_names[:3])}...", "warning")
                        # Allow execution anyway for now, but log the issue
                    
                    self.log(f"Executing: {tool_name}", "info")
                    
                    # Parse server name and actual tool name
                    server_name, actual_tool_name = tool_name.split('.', 1) if '.' in tool_name else (None, tool_name)
                    
                    if not server_name or server_name not in self.client.sessions:
                        error_msg = f"Unknown server for tool {tool_name}"
                        self.log(error_msg, "error")
                        if attempt < max_retries - 1:
                            continue  # Retry with different tool selection
                        else:
                            summary = error_msg
                            break
                    
                    try:
                        # Call the tool via MCP session (exact same way as client.py)
                        result = await self.client.sessions[server_name]["session"].call_tool(
                            actual_tool_name,
                            tool_args
                        )
                        
                        tool_response = f"{result.content[0].text}"
                        
                        tool_results.append({
                            "tool": tool_name,
                            "arguments": tool_args,
                            "result": tool_response
                        })
                        
                        self.log(f"✓ Tool executed successfully", "success")
                        execution_success = True
                        
                        # Generate summary from result
                        summary = await self._generate_summary(description, tool_results)
                        break  # Success, no need to retry
                        
                    except Exception as e:
                        error_msg = f"Tool execution error: {e}"
                        self.log(error_msg, "error")
                        if attempt < max_retries - 1:
                            self.log("Will retry with same or different tool", "info")
                            continue  # Retry
                        else:
                            summary = f"Failed to execute tool after {max_retries} attempts: {e}"
                            break
                
                if execution_success:
                    break  # Successfully executed, exit retry loop
                        
            except Exception as e:
                self.log(f"Execution error: {e}", "error")
                if attempt < max_retries - 1:
                    continue  # Retry
                else:
                    summary = f"Critical error: {e}"
                    break
        
        # Ensure we have a summary
        if not summary and not tool_results:
            summary = f"Task '{description}' completed without tool execution"
            
        # Update step status
        self.context_manager.update_step_status(
            step_id,
            "completed",
            {"tool_results": tool_results, "summary": summary}
        )
        
        # Add summary to context
        self.context_manager.add_execution_summary(f"Task {step_id}: {summary}")
        
        self.log(f"✓ Task {step_id} completed", "success")
        
        return {
            "step_id": step_id,
            "results": tool_results,
            "summary": summary
        }
        
    async def _generate_summary(self, task: str, tool_results: List[Dict]) -> str:
        """
        Generate concise summary of tool execution results
        """
        if not tool_results:
            return f"Task '{task}' completed without tool execution"
        
        # Build summary from tool results (extract key information)
        results_text = []
        for result in tool_results:
            tool_name = result['tool']
            result_data = str(result.get('result', 'No result'))[:5000]  # Increased limit for complete results
            
            # Extract key info from result
            lines = result_data.split('\n')
            # Keep first 50 lines and last 20 lines to capture important info
            if len(lines) > 70:
                key_lines = lines[:50] + ['...'] + lines[-20:]
                result_data = '\n'.join(key_lines)
            
            results_text.append(f"Tool: {tool_name}\nResult:\n{result_data}")
            
        prompt = f"""Analyze and summarize these tool execution results in Chinese:

Task: {task}

Tool Execution Results:
{chr(10).join(results_text)}

Provide a concise summary in Chinese (max 100 words):
- 关键发现（端口状态、服务、漏洞等）
- 重要数据（IP、端口号、版本信息）
- 任务完成状态

ONLY output the summary, no extra text."""

        try:
            summary = await self.call_model(prompt, max_tokens=2000)
            if summary and summary.strip():
                return summary.strip()
            else:
                # Fallback: extract basic info from result
                return self._extract_basic_summary(task, tool_results)
        except Exception as e:
            self.log(f"Summary generation failed: {e}", "warning")
            return self._extract_basic_summary(task, tool_results)
    
    def _extract_basic_summary(self, task: str, tool_results: List[Dict]) -> str:
        """Fallback: Extract basic summary without LLM"""
        tool_names = [r['tool'] for r in tool_results]
        result_preview = str(tool_results[0].get('result', ''))[:2000] if tool_results else 'No results'
        return f"已执行工具: {', '.join(tool_names)}\n任务: {task}\n完整结果:\n{result_preview}"
