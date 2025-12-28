# UltraRAG 知识库集成指南

本指南介绍如何在 `ollama_mcp` 中启用 UltraRAG 知识库，使本地 Ollama 模型可以通过 MCP 工具直接检索 UltraRAG 构建的语料。

## 1. 安装依赖

UltraRAG 的检索器依赖 `sentence-transformers`、`faiss` 等包。建议在当前环境运行：

```bash
cd /disk1/users/user/ollama_mcp
pip install -r ultrarag_requirements.txt
```

> 💡 如果你希望使用 GPU，请按需安装对应的 `faiss-gpu-cuXX` 包，并设置 `ULTRARAG_GPU_IDS`。

## 2. 指定 UltraRAG 仓库位置

默认路径为 `/disk1/users/user/UltraRAG`。若你的仓库位于其它位置，请在 shell 中设置：

```bash
export ULTRARAG_ROOT=/path/to/UltraRAG
```

也可以在 `ultrarag_mcp_config.json` 里修改 `env.ULTRARAG_ROOT`。

## 3. 准备语料与索引

UltraRAG 的 `servers/retriever/parameter.yaml` 默认指向 `data/corpus_example.jsonl`。你可以：

1. 直接使用示例语料；
2. 按 UltraRAG 文档构建自己的 `corpus.jsonl`、`embedding.npy`、`index/index.index`。

当 `ultrarag_mcp_server.py` 第一次启动时，如果检测到嵌入或索引不存在，它会自动：

1. 调用 UltraRAG 的 `retriever_embed` 生成向量；
2. 调用 `retriever_index` 构建 FAISS 索引。

## 4. 启动 UltraRAG MCP Server

```bash
cd /disk1/users/user/ollama_mcp
python3 ultrarag_mcp_server.py
```

成功后可在另一终端运行 `ollmcp`。

## 5. 在 Ollama MCP 客户端中启用

使用提供的配置文件 `ultrarag_mcp_config.json`，或者将其中的条目合并至你自己的 `servers.json`：

```json
{
  "mcpServers": {
    "ultrarag-knowledge-base": {
      "command": "python3",
      "args": ["/disk1/users/user/ollama_mcp/ultrarag_mcp_server.py"],
      "env": {
        "PYTHONPATH": "/disk1/users/user/ollama_mcp",
        "ULTRARAG_ROOT": "/disk1/users/user/UltraRAG"
      }
    }
  }
}
```

然后运行：

```bash
ollmcp --servers-json /disk1/users/user/ollama_mcp/ultrarag_mcp_config.json
```

## 6. 可用工具

| 工具名 | 说明 | 参数 |
| --- | --- | --- |
| `search_ultrarag_knowledge` | 检索 UltraRAG 语料，并返回排序后的段落 | `query` (必填), `top_k` (可选，默认 5，最大 20) |
| `get_ultrarag_stats` | 查看语料、索引、编码器等配置 | 无 |

### 示例对话

```
你：请从 UltraRAG 知识库里找出与 Kansas City Chiefs 相关的背景资料
AI：调用 search_ultrarag_knowledge -> 返回多个段落及来源信息
```

## 7. 常见问题

- **导入失败 / 缺少依赖**：确认执行过 `pip install -r ultrarag_requirements.txt`，并在同一环境运行。
- **找不到语料文件**：检查 `servers/retriever/parameter.yaml` 中的 `corpus_path`，确保路径存在。
- **索引过期或损坏**：删除 `embedding/` 与 `index/` 目录后重新启动 `ultrarag_mcp_server.py`，它会自动重建。

完成以上步骤后，Ollama 模型即可通过 MCP 工具直接调用 UltraRAG 提供的知识库，实现 “本地推理 + UltraRAG 检索” 的组合能力。

