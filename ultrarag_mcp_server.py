#!/usr/bin/env python3
"""
Expose the UltraRAG knowledge base as an MCP server so ollmcp can call it.
"""

from __future__ import annotations

import asyncio
import os
from typing import Any, Dict, List

from mcp.server import NotificationOptions, Server
from mcp.server.models import InitializationOptions
import mcp.server.stdio
import mcp.types as types

from ultrarag_integration import UltraRAGIntegrationError, UltraRAGKnowledgeBase


def _build_kb() -> UltraRAGKnowledgeBase:
    cfg_override = os.environ.get("ULTRARAG_RETRIEVER_CONFIG")
    root_override = os.environ.get("ULTRARAG_ROOT")
    return UltraRAGKnowledgeBase(
        ultrarag_root=root_override,
        config_path=cfg_override,
    )


try:
    KB = _build_kb()
except UltraRAGIntegrationError as exc:  # pragma: no cover - runtime failure
    raise SystemExit(
        "Failed to initialise UltraRAG knowledge base integration.\n"
        f"{exc}\n"
        "Set ULTRARAG_ROOT to the UltraRAG repository and ensure the retriever\n"
        "dependencies are installed. Refer to ULTRARAG_INTEGRATION.md for help."
    ) from exc


server = Server("ultrarag-knowledge-base")


@server.list_tools()
async def list_tools() -> List[types.Tool]:
    return [
        types.Tool(
            name="search_ultrarag_knowledge",
            description="Query the UltraRAG corpus and return the top passages.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Natural-language question or keywords.",
                    },
                    "top_k": {
                        "type": "integer",
                        "description": "How many passages to return (default 5).",
                        "minimum": 1,
                        "maximum": 20,
                        "default": 5,
                    },
                },
                "required": ["query"],
            },
        ),
        types.Tool(
            name="get_ultrarag_stats",
            description="Report the UltraRAG retriever configuration and corpus info.",
            inputSchema={"type": "object", "properties": {}, "required": []},
        ),
    ]


def _format_passages(rows: List[Dict[str, Any]], query: str) -> str:
    if not rows:
        return f"No UltraRAG passages matched '{query}'."
    lines = [
        f"UltraRAG search results for: {query}",
        "-" * 60,
    ]
    for row in rows:
        meta = row.get("metadata") or {}
        lines.append(f"[{row['rank']}] doc_id={row.get('id', 'N/A')}")
        title = row.get("title") or meta.get("title")
        if title:
            lines.append(f"Title: {title}")
        origin = meta.get("origin") or meta.get("source")
        if origin:
            lines.append(f"Source: {origin}")
        lines.append(row["content"])
        lines.append("-" * 60)
    return "\n".join(lines)


@server.call_tool()
async def call_tool(
    name: str, arguments: Dict[str, Any] | None
) -> List[types.TextContent]:
    if name == "search_ultrarag_knowledge":
        if not arguments or not isinstance(arguments, dict):
            raise ValueError("search_ultrarag_knowledge expects arguments.")
        query = arguments.get("query")
        if not query:
            raise ValueError("The 'query' field is required.")
        top_k = arguments.get("top_k", 5)
        rows = await KB.search(query=query, top_k=top_k)
        payload = _format_passages(rows, query)
        return [types.TextContent(type="text", text=payload)]

    if name == "get_ultrarag_stats":
        stats = KB.stats()
        lines = [
            "UltraRAG knowledge base stats",
            "-" * 60,
            f"Documents     : {stats['documents']}",
            f"Corpus file   : {stats['corpus_path']}",
            f"Embedding file: {stats['embedding_path']}",
            f"Index file    : {stats['index_path']}",
            f"Encoder       : {stats['backend']}",
            f"Index backend : {stats['index_backend']}",
            f"Instruction   : {stats['query_instruction'] or '<none>'}",
        ]
        return [types.TextContent(type="text", text="\n".join(lines))]

    raise ValueError(f"Unknown tool requested: {name}")


async def main() -> None:
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="ultrarag-knowledge-base",
                server_version="1.0.0",
                capabilities=server.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                ),
            ),
        )


if __name__ == "__main__":
    asyncio.run(main())

