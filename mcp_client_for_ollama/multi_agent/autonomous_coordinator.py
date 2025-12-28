"""
Autonomous Multi-Agent Coordinator
Implements continuous decision-action-evaluation loop
"""

from typing import Dict, Any, Optional
from rich.console import Console
from .strategy_agent import StrategyAgent
from .selector_agent import ToolSelectorAgent
from .executor_agent import ExecutorAgent
from .context_manager import SharedContextManager
import time


class AutonomousCoordinator:
    """
    Autonomous Multi-Agent System Coordinator
    
    Workflow:
    1. User provides high-level goal
    2. Strategy Agent analyzes and decides next action
    3. Tool Selector filters relevant tools
    4. Executor runs tools and returns results
    5. Strategy Agent evaluates results
    6. Loop continues until Strategy Agent decides to finish
    
    This enables:
    - Natural language queries without explicit steps
    - Adaptive behavior based on discoveries
    - Autonomous decision making
    - Self-terminating when goals achieved
    """
    
    def __init__(
        self,
        model: str,
        console: Console,
        tool_manager,
        client,
        flag_validator=None
    ):
        self.model = model
        self.console = console
        self.tool_manager = tool_manager
        self.client = client
        self.flag_validator = flag_validator  # Flag验证器
        
        # Initialize shared context
        self.context_manager = SharedContextManager()
        
        # Initialize agents
        self.strategy = StrategyAgent(model, console, self.context_manager)
        self.selector = ToolSelectorAgent(model, console, self.context_manager, tool_manager)
        self.executor = ExecutorAgent(model, console, self.context_manager, client)
        
        self.console.print("[green]✓ Autonomous Multi-Agent system initialized[/green]")
        self.console.print(f"[cyan]  - Strategy Agent: {model} (决策与协调)[/cyan]")
        self.console.print(f"[cyan]  - Tool Selector: {model} (工具筛选)[/cyan]")
        self.console.print(f"[cyan]  - Executor: {model} (工具执行)[/cyan]")
        
        if self.flag_validator:
            self.console.print(f"[cyan]  - Flag Validator: 已启用 (自动验证flag)[/cyan]")
        
    async def process_query(self, query: str) -> str:
        """
        Process query through autonomous decision loop
        
        The Strategy Agent continuously:
        1. Analyzes current state
        2. Decides next action
        3. Coordinates execution
        4. Evaluates results
        5. Repeats until goal achieved
        """
        # 记录开始时间用于统计
        start_time = time.time()
        
        # 如果启用了flag验证器，获取当前测试的CVE编号
        current_cve = None
        if self.flag_validator:
            current_cve = self.flag_validator.get_current_cve()
            if current_cve:
                self.console.print(f"\n[bold yellow]🎯 当前测试: {current_cve}[/bold yellow]")
                self.console.print(f"[cyan]{self.flag_validator.get_test_progress()}[/cyan]\n")
        
        self.console.print(f"\n[bold cyan]{'='*70}[/bold cyan]")
        self.console.print(f"[bold cyan]🤖 Autonomous Multi-Agent System Processing[/bold cyan]")
        self.console.print(f"[bold cyan]{'='*70}[/bold cyan]\n")
        self.console.print(f"[yellow]User Goal:[/yellow] {query}\n")
        
        # Store original query in context
        self.context_manager.original_query = query
        
        # Execution history for decision making
        execution_history = []
        
        # Maximum iterations to prevent infinite loops
        max_iterations = 15
        iteration = 0
        
        # Main autonomous decision loop
        while iteration < max_iterations:
            iteration += 1
            
            self.console.print(f"\n[bold yellow]━━━ Iteration {iteration}/{max_iterations} ━━━[/bold yellow]\n")
            
            # Stage 1: Strategy Agent decides next action
            self.console.print("[bold magenta]🧠 Strategy Agent: Analyzing & Deciding...[/bold magenta]")
            
            decision = await self.strategy.decide_next_action(
                user_query=query,
                execution_history=execution_history,
                iteration=iteration
            )
            
            decision_type = decision.get("decision", "unknown")
            reasoning = decision.get("reasoning", "No reasoning provided")
            
            self.console.print(f"[cyan]Decision:[/cyan] {decision_type.upper()}")
            self.console.print(f"[cyan]Reasoning:[/cyan] {reasoning}\n")
            
            # Check if Strategy Agent decided to finish
            if decision_type == "finish":
                self.console.print("[green]✓ Strategy Agent determined task is complete[/green]\n")
                
                # Get summary from decision or generate report
                final_summary = decision.get("final_summary", "")
                
                if not final_summary or len(final_summary) < 50:
                    # Generate comprehensive final report
                    self.console.print("[bold yellow]📝 Generating Final Report...[/bold yellow]\n")
                    final_report = await self.strategy.generate_final_report(
                        user_query=query,
                        execution_history=execution_history
                    )
                else:
                    final_report = final_summary
                
                # Flag验证处理
                if self.flag_validator and current_cve:
                    self.console.print(f"\n[bold yellow]🔍 验证Flag...[/bold yellow]")
                    
                    # 验证flag
                    is_correct, extracted_flag, expected_flag = self.flag_validator.validate_flag(
                        final_report, current_cve
                    )
                    
                    # 显示验证结果
                    if is_correct:
                        self.console.print(f"[bold green]✓ Flag验证成功![/bold green]")
                        self.console.print(f"[green]提取的Flag: {extracted_flag}[/green]")
                    else:
                        self.console.print(f"[bold red]✗ Flag验证失败![/bold red]")
                        self.console.print(f"[yellow]提取的Flag: {extracted_flag if extracted_flag else '(未提取到flag)'}[/yellow]")
                        self.console.print(f"[green]正确的Flag: {expected_flag}[/green]")
                    
                    # 记录测试结果
                    elapsed_time = time.time() - start_time
                    self.flag_validator.record_test_result(
                        cve_id=current_cve,
                        model_response=final_report,
                        is_success=is_correct,
                        extracted_flag=extracted_flag,
                        expected_flag=expected_flag,
                        elapsed_time=elapsed_time
                    )
                    
                    # 显示当前统计
                    self.flag_validator.display_current_stats()
                    
                    # 移动到下一个测试
                    self.flag_validator.next_test()
                
                self.console.print(f"[bold cyan]{'='*70}[/bold cyan]")
                self.console.print(f"[bold green]✓ Task Completed ({iteration} iterations)[/bold green]")
                self.console.print(f"[bold cyan]{'='*70}[/bold cyan]\n")
                
                # Display final report with markdown
                from rich.markdown import Markdown
                self.console.print(Markdown(final_report))
                
                return final_report
                
            # Extract next task
            next_task = decision.get("next_task", {})
            task_description = next_task.get("description", "Unknown task")
            tool_keywords = next_task.get("tool_keywords", [])
            
            self.console.print(f"[yellow]Next Task:[/yellow] {task_description}")
            self.console.print(f"[yellow]Keywords:[/yellow] {', '.join(tool_keywords)}\n")
            
            # Stage 2: Tool Selector filters relevant tools
            self.console.print("[bold magenta]🔍 Tool Selector: Filtering tools...[/bold magenta]")
            
            selection_result = await self.selector.process({
                "step_id": iteration,
                "description": task_description,
                "keywords": tool_keywords
            })
            
            selected_tool_count = selection_result.get("tool_count", 0)
            
            if selected_tool_count == 0:
                self.console.print("[yellow]⚠ No tools selected, asking Strategy Agent to reconsider[/yellow]\n")
                execution_history.append({
                    "task": task_description,
                    "summary": "No suitable tools found for this task."
                })
                continue
                
            # Stage 3: Executor runs selected tools
            self.console.print(f"[bold magenta]⚡ Executor: Running {selected_tool_count} tools...[/bold magenta]\n")
            
            # Get tool objects from selector's message
            messages = self.context_manager.get_messages_for_agent("ExecutorAgent")
            tool_objects = []
            for msg in messages:
                if msg.message_type == "tool_selection":
                    tool_objects = msg.content.get("tool_objects", [])
                    break
                    
            execution_result = await self.executor.process({
                "step_id": iteration,
                "description": task_description,
                "tool_objects": tool_objects
            })
            
            summary = execution_result.get("summary", "No summary generated")
            
            self.console.print(f"\n[green]✓ Iteration {iteration} completed[/green]")
            self.console.print(f"[cyan]Summary:[/cyan] {summary[:200]}...\n")
            
            # Add to execution history for next decision
            execution_history.append({
                "task": task_description,
                "summary": summary,
                "results": execution_result.get("results", [])
            })
            
        # Max iterations reached
        self.console.print(f"\n[yellow]⚠ Maximum iterations ({max_iterations}) reached[/yellow]\n")
        
        # Generate final report even at max iterations
        self.console.print("[bold yellow]📝 Generating Final Report...[/bold yellow]\n")
        final_report = await self.strategy.generate_final_report(
            user_query=query,
            execution_history=execution_history
        )
        
        # Flag验证处理（即使达到最大迭代次数也要验证）
        if self.flag_validator and current_cve:
            self.console.print(f"\n[bold yellow]🔍 验证Flag...[/bold yellow]")
            
            # 验证flag
            is_correct, extracted_flag, expected_flag = self.flag_validator.validate_flag(
                final_report, current_cve
            )
            
            # 显示验证结果
            if is_correct:
                self.console.print(f"[bold green]✓ Flag验证成功![/bold green]")
                self.console.print(f"[green]提取的Flag: {extracted_flag}[/green]")
            else:
                self.console.print(f"[bold red]✗ Flag验证失败![/bold red]")
                self.console.print(f"[yellow]提取的Flag: {extracted_flag if extracted_flag else '(未提取到flag)'}[/yellow]")
                self.console.print(f"[green]正确的Flag: {expected_flag}[/green]")
            
            # 记录测试结果
            elapsed_time = time.time() - start_time
            self.flag_validator.record_test_result(
                cve_id=current_cve,
                model_response=final_report,
                is_success=is_correct,
                extracted_flag=extracted_flag,
                expected_flag=expected_flag,
                elapsed_time=elapsed_time
            )
            
            # 显示当前统计
            self.flag_validator.display_current_stats()
            
            # 移动到下一个测试
            self.flag_validator.next_test()
        
        self.console.print(f"[bold cyan]{'='*70}[/bold cyan]")
        self.console.print(f"[bold yellow]⚠ Task ended at max iterations ({len(execution_history)} tasks completed)[/bold yellow]")
        self.console.print(f"[bold cyan]{'='*70}[/bold cyan]\n")
        
        # Display final report with markdown
        from rich.markdown import Markdown
        self.console.print(Markdown(final_report))
        
        return final_report
