# RAG知识库使用指南

## 概述

这是一个集成到ollama_mcp项目中的RAG（检索增强生成）知识库系统，用于让本地大语言模型能够查询安全漏洞知识库。

> 🆕 如果你希望直接复用 UltraRAG 的 retriever 及其 YAML 配置，
> 请参考 `ULTRARAG_INTEGRATION.md`。新的 `ultrarag_mcp_server.py`
> 可以将 UltraRAG 知识库以 MCP 工具形式暴露给 `ollmcp`。

## 系统架构

```
rag_knowledge_base/
├── __init__.py              # 模块初始化
├── document_processor.py    # 文档加载和分块
├── vector_store.py          # ChromaDB向量存储
└── rag_retriever.py         # RAG检索器

rag_mcp_server.py            # MCP服务器（提供工具接口）
build_knowledge_base.py      # 知识库构建脚本
rag_mcp_config.json          # MCP服务器配置
rag_requirements.txt         # Python依赖
```

## 安装依赖

```bash
cd /disk1/users/user/ollama_mcp
pip install -r rag_requirements.txt
```

## 构建知识库

### 1. 确保Ollama已安装并运行

```bash
# 检查Ollama是否运行
ollama list

# 确保nomic-embed-text模型已安装（用于生成嵌入向量）
ollama pull nomic-embed-text
```

### 2. 运行知识库构建脚本

```bash
cd /disk1/users/user/ollama_mcp

# 基本构建
python3 build_knowledge_base.py

# 重建数据库（清空现有数据）
python3 build_knowledge_base.py --rebuild

# 构建后运行测试
python3 build_knowledge_base.py --test

# 自定义文档目录和数据库路径
python3 build_knowledge_base.py \
  --docs-dir /path/to/markdown/files \
  --db-path ./custom_chroma_db
```

### 3. 等待索引完成

脚本会：
- 加载所有markdown文件
- 提取元数据（标题、CVE ID、来源等）
- 将文档分块（默认1000字符，重叠200字符）
- 生成嵌入向量
- 存储到ChromaDB

## 使用RAG工具

### 方式1：通过ollmcp客户端使用

1. 配置MCP服务器：

```bash
# 方式A：使用提供的配置文件
export MCP_CONFIG=/disk1/users/user/ollama_mcp/rag_mcp_config.json

# 方式B：添加到你的MCP配置中
# 编辑 ~/.config/mcp/servers.json 或你的配置文件
```

配置内容示例：
```json
{
  "mcpServers": {
    "rag-knowledge-base": {
      "command": "python3",
      "args": [
        "/disk1/users/user/ollama_mcp/rag_mcp_server.py"
      ],
      "env": {
        "PYTHONPATH": "/disk1/users/user/ollama_mcp"
      }
    }
  }
}
```

2. 启动ollmcp：

```bash
cd /disk1/users/user/ollama_mcp
python3 -m mcp_client_for_ollama.cli
```

3. 在对话中使用：

```
你: 查询CVE-2024-0012的详细信息
AI: [会自动调用search_security_knowledge工具查询知识库]

你: Palo Alto防火墙有哪些远程命令执行漏洞？
AI: [会自动调用search_security_knowledge工具]
```

### 方式2：直接使用Python API

```python
from rag_knowledge_base.vector_store import VectorStore
from rag_knowledge_base.rag_retriever import RAGRetriever

# 初始化
vector_store = VectorStore(
    persist_directory="./chroma_db",
    collection_name="security_knowledge",
    embedding_model="nomic-embed-text"
)

rag_retriever = RAGRetriever(vector_store=vector_store)

# 搜索
results = rag_retriever.retrieve("CVE-2024-0012", n_results=3)

# 格式化输出
context = rag_retriever.retrieve_with_context("Palo Alto防火墙漏洞", n_results=5)
print(context)
```

## 可用的MCP工具

### 1. search_security_knowledge

搜索安全漏洞知识库。

**参数：**
- `query` (必需): 查询内容，可以是漏洞描述、CVE ID、产品名称等
- `n_results` (可选): 返回结果数量，默认3，范围1-10
- `filter_cve` (可选): 按CVE ID过滤，例如 "CVE-2024-0012"

**示例：**
```json
{
  "query": "Palo Alto防火墙身份认证绕过",
  "n_results": 5
}
```

### 2. get_knowledge_base_stats

获取知识库统计信息。

**参数：** 无

**返回：** 集合名称、文档数量、存储路径等信息

## 配置选项

### 文档分块参数

在 `RAGRetriever` 初始化时可以调整：

```python
rag_retriever = RAGRetriever(
    vector_store=vector_store,
    chunk_size=1000,      # 每块字符数
    chunk_overlap=200     # 块之间重叠字符数
)
```

### 嵌入模型

在 `VectorStore` 初始化时可以更换：

```python
vector_store = VectorStore(
    persist_directory="./chroma_db",
    collection_name="security_knowledge",
    embedding_model="nomic-embed-text"  # 或其他Ollama支持的embedding模型
)
```

推荐的embedding模型：
- `nomic-embed-text` (默认，133MB，性能好)
- `mxbai-embed-large` (670MB，更精确)
- `all-minilm` (46MB，轻量级)

## 性能优化

### 1. 批量索引

脚本默认使用批处理（batch_size=100），大规模文档建议增加批次大小：

```python
vector_store.add_documents(documents, batch_size=200)
```

### 2. 并行查询

如果需要处理多个查询，可以使用异步：

```python
import asyncio

async def search_multiple(queries):
    tasks = [rag_retriever.retrieve(q, n_results=3) for q in queries]
    return await asyncio.gather(*tasks)
```

## 故障排查

### 问题1：Ollama连接失败

```bash
# 确保Ollama正在运行
systemctl status ollama
# 或
ps aux | grep ollama

# 检查Ollama API
curl http://localhost:11434/api/tags
```

### 问题2：embedding模型不存在

```bash
# 拉取模型
ollama pull nomic-embed-text
```

### 问题3：ChromaDB权限错误

```bash
# 确保数据库目录可写
chmod -R 755 /disk1/users/user/ollama_mcp/chroma_db
```

### 问题4：内存不足

- 减少batch_size
- 减少chunk_size
- 使用更小的embedding模型

## 维护

### 更新知识库

```bash
# 添加新文档（不清空现有数据）
python3 build_knowledge_base.py

# 完全重建
python3 build_knowledge_base.py --rebuild
```

### 清空知识库

```python
from rag_knowledge_base.vector_store import VectorStore

vector_store = VectorStore(persist_directory="./chroma_db")
vector_store.delete_all()
```

### 备份知识库

```bash
# 备份ChromaDB目录
tar -czf chroma_db_backup_$(date +%Y%m%d).tar.gz chroma_db/
```

## 高级用法

### 自定义元数据过滤

```python
# 按来源过滤
results = rag_retriever.retrieve(
    query="防火墙漏洞",
    n_results=5,
    filter_cve="CVE-2024-0012"
)
```

### 获取原始ChromaDB结果

```python
# 直接使用VectorStore
results = vector_store.search(
    query="远程代码执行",
    n_results=10,
    filter_dict={"origin": "blog.csdn.net"}
)
```

## 许可证

MIT License - 与ollama_mcp项目保持一致
