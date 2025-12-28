"""
Helpers that let the ollama_mcp project talk to the UltraRAG knowledge base.

The integration is designed so that we do not need to modify the upstream
UltraRAG repo.  Instead we import the retriever server components directly,
load the YAML parameter file, and expose a tiny API that other modules inside
this project can reuse (for example the MCP server shim).
"""

from .knowledge_base import UltraRAGKnowledgeBase, UltraRAGIntegrationError

__all__ = ["UltraRAGKnowledgeBase", "UltraRAGIntegrationError"]

