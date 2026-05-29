#!/usr/bin/env python3
"""
MCP Server for RAG Knowledge Base
为ollama_mcp提供RAG知识库查询工具
"""

import asyncio
import os
from typing import Any
from mcp.server.models import InitializationOptions
import mcp.types as types
from mcp.server import NotificationOptions, Server
import mcp.server.stdio

from rag_knowledge_base.vector_store import VectorStore
from rag_knowledge_base.rag_retriever import RAGRetriever


# 初始化RAG系统
RAG_DB_PATH = os.path.join(os.path.dirname(__file__), "chroma_db")
VECTOR_STORE = VectorStore(
    persist_directory=RAG_DB_PATH,
    collection_name="security_knowledge",
    embedding_model="nomic-embed-text"
)
RAG_RETRIEVER = RAGRetriever(vector_store=VECTOR_STORE)

# 创建MCP服务器
server = Server("rag-knowledge-base")


@server.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    """列出可用的RAG工具"""
    return [
        types.Tool(
            name="search_security_knowledge",
            description="搜索安全漏洞知识库，查找相关的CVE漏洞信息、漏洞详情、利用方法等。支持查询Palo Alto Networks相关的安全漏洞。",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "查询内容，可以是漏洞描述、CVE ID、产品名称等"
                    },
                    "n_results": {
                        "type": "integer",
                        "description": "返回结果数量，默认为3",
                        "default": 3,
                        "minimum": 1,
                        "maximum": 10
                    },
                    "filter_cve": {
                        "type": "string",
                        "description": "可选：按CVE ID过滤结果，例如 'CVE-2024-0012'"
                    }
                },
                "required": ["query"]
            }
        ),
        types.Tool(
            name="get_knowledge_base_stats",
            description="获取RAG知识库的统计信息，包括文档数量、集合名称等。",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        )
    ]


@server.call_tool()
async def handle_call_tool(
    name: str, arguments: dict | None
) -> list[types.TextContent | types.ImageContent | types.EmbeddedResource]:
    """处理工具调用"""
    
    if name == "search_security_knowledge":
        if not arguments:
            raise ValueError("缺少查询参数")
        
        query = arguments.get("query")
        if not query:
            raise ValueError("查询内容不能为空")
        
        n_results = arguments.get("n_results", 3)
        filter_cve = arguments.get("filter_cve")
        
        # 如果有CVE过滤但查询只是CVE ID，尝试读取文档标题来增强查询
        enhanced_query = query
        if filter_cve and filter_cve in query and len(query) < 30:
            # 查询太短且包含CVE ID，尝试找到对应文档
            # 先做一次宽松搜索
            try:
                temp_results = RAG_RETRIEVER.retrieve(query=query, n_results=50, filter_cve=None)
                for r in temp_results:
                    if filter_cve in r['metadata'].get('cve_ids', ''):
                        # 找到了，用标题增强查询
                        title = r['metadata'].get('title', '')
                        if title and len(title) > 10:
                            enhanced_query = f"{query} {title}"
                            break
            except:
                pass  # 如果增强失败，使用原查询
        
        try:
            # 检索知识库
            results = RAG_RETRIEVER.retrieve(
                query=enhanced_query,
                n_results=n_results,
                filter_cve=filter_cve
            )
            
            if not results:
                return [
                    types.TextContent(
                        type="text",
                        text=f"未找到与 '{query}' 相关的文档。"
                    )
                ]
            
            # 格式化结果
            response_parts = [f"找到 {len(results)} 个相关文档：\n"]
            
            for i, result in enumerate(results, 1):
                metadata = result['metadata']
                content = result['content']
                distance = result.get('distance', 0)
                similarity = 1 - distance if distance else 1.0
                
                response_parts.append(f"\n{'='*60}")
                response_parts.append(f"文档 {i} (相似度: {similarity:.2%})")
                response_parts.append(f"{'='*60}")
                
                if 'title' in metadata:
                    response_parts.append(f"📄 标题: {metadata['title']}")
                
                if 'cve_ids' in metadata:
                    response_parts.append(f"🔒 CVE: {metadata['cve_ids']}")
                
                if 'origin' in metadata:
                    response_parts.append(f"🌐 来源: {metadata['origin']}")
                
                if 'date' in metadata:
                    response_parts.append(f"📅 日期: {metadata['date']}")
                
                response_parts.append(f"📁 文件: {metadata.get('filename', '未知')}")
                response_parts.append(f"\n📝 内容:\n{content[:500]}...")
                response_parts.append("")
            
            return [
                types.TextContent(
                    type="text",
                    text="\n".join(response_parts)
                )
            ]
            
        except Exception as e:
            return [
                types.TextContent(
                    type="text",
                    text=f"搜索失败: {str(e)}"
                )
            ]
    
    elif name == "get_knowledge_base_stats":
        try:
            stats = RAG_RETRIEVER.get_stats()
            
            response = f"""
RAG知识库统计信息
{'='*60}
📚 集合名称: {stats['collection_name']}
📊 文档数量: {stats['document_count']}
💾 存储路径: {stats['persist_directory']}
{'='*60}
"""
            return [
                types.TextContent(
                    type="text",
                    text=response
                )
            ]
        except Exception as e:
            return [
                types.TextContent(
                    type="text",
                    text=f"获取统计信息失败: {str(e)}"
                )
            ]
    
    else:
        raise ValueError(f"未知工具: {name}")


async def main():
    """运行MCP服务器"""
    # 使用stdio传输
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="rag-knowledge-base",
                server_version="1.0.0",
                capabilities=server.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                ),
            ),
        )


if __name__ == "__main__":
    asyncio.run(main())
