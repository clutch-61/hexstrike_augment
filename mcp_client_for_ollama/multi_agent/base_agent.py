"""
Base Agent Class
Common functionality for all agents in the multi-agent system
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from rich.console import Console
import ollama


class BaseAgent(ABC):
    """
    Abstract base class for all agents
    Each agent has a specific role and operates with a subset of context
    """
    
    def __init__(
        self,
        name: str,
        model: str,
        console: Console,
        context_manager: 'SharedContextManager',
        system_prompt: str = ""
    ):
        self.name = name
        self.model = model
        self.console = console
        self.context_manager = context_manager
        self.system_prompt = system_prompt
        self.ollama = ollama.AsyncClient()
        
    @abstractmethod
    async def process(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process input and return output
        Each agent implements its own processing logic
        """
        pass
        
    async def call_model(
        self,
        user_message: str,
        additional_context: Optional[str] = None,
        max_tokens: int = 4000
    ) -> str:
        """
        Call the LLM with a user message
        Automatically includes system prompt and limits response length
        """
        messages = []
        
        # Build system prompt
        full_system_prompt = self.system_prompt
        if additional_context:
            full_system_prompt += f"\n\nCurrent Context:\n{additional_context}"
            
        if full_system_prompt:
            messages.append({
                "role": "system",
                "content": full_system_prompt
            })
            
        messages.append({
            "role": "user",
            "content": user_message
        })
        
        try:
            # Call model without streaming for inter-agent communication
            response = await self.ollama.chat(
                model=self.model,
                messages=messages,
                options={
                    "num_predict": max_tokens,
                    "temperature": 0.7
                }
            )
            
            content = response.get('message', {}).get('content', '')
            
            # Log if response is empty
            if not content:
                self.log(f"⚠ Model returned empty response for: {user_message[:100]}...", "warning")
                
            return content
            
        except Exception as e:
            self.log(f"Model call failed: {e}", "error")
            return ""
        
    def log(self, message: str, level: str = "info"):
        """Log agent activity"""
        color_map = {
            "info": "cyan",
            "success": "green",
            "warning": "yellow",
            "error": "red",
            "debug": "dim"
        }
        color = color_map.get(level, "white")
        self.console.print(f"[{color}][{self.name}] {message}[/{color}]")
        
    def get_token_estimate(self, text: str) -> int:
        """Estimate token count (rough approximation)"""
        return len(text) // 4
