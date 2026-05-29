#!/bin/bash

# Ollama MCP 客户端 - 自主多代理模式启动脚本
# 支持 HexStrike AI + RAG知识库 + 自主决策三层代理架构

echo "🚀 启动 Ollama MCP 客户端（自主多代理模式）..."
echo ""
echo "🤖 自主三层代理架构："
echo "  🧠 Strategy Agent  - 自主决策与任务协调（分析→决策→执行→评估）"
echo "  🎯 Selector Agent  - 智能工具筛选（152→8工具）"
echo "  ⚡ Executor Agent  - 工具执行与结果汇总"
echo ""
echo "✨ 核心特性："
echo "  • 自然语言输入：无需明确步骤，AI自主分解任务"
echo "  • 自适应执行：根据结果动态调整策略"
echo "  • 自主决策：判断何时继续、何时完成"
echo "  • 持续学习：每次执行后重新评估下一步"
echo ""
echo "📦 已启用的服务："
echo "  1. 🛡️  HexStrike AI - 网络安全自动化平台（109个工具）"
echo "  2. 📚 RAG Knowledge Base - Palo Alto漏洞知识库（43个工具）"
echo ""

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_FILE="${SCRIPT_DIR}/hexstrike-with-rag-config.json"

# 默认模型
MODEL="qwen3:32b"

# Token优化信息
echo "💾 Token优化："
echo "  ✅ 传统模式: 152工具 × 115 tokens = 17,480 tokens基础开销"
echo "  ✅ 自主模式: 每次只加载8个相关工具 = ~920 tokens"
echo "  ✅ 节省率: 94.7% → 支持10+次迭代决策循环"
echo ""
echo "📋 配置文件: $CONFIG_FILE"
echo "🤖 默认模型: $MODEL"
echo ""
echo "💡 使用方法："
echo "  1️⃣  输入 'ma' 命令启用自主多代理模式"
echo "  2️⃣  直接用自然语言提问："
echo "      > 请扫描10.81.0.64:8209端口，分析其中可能有什么漏洞"
echo "      > 帮我测试这个目标是否存在CVE-2020-17519"
echo "      > 对192.168.1.100进行全面的安全评估"
echo "  3️⃣  Strategy Agent会自主："
echo "      • 分析任务并决定第一步做什么"
echo "      • 执行后评估结果"
echo "      • 决定下一步或结束"
echo ""
echo "📖 详细文档: MULTI_AGENT_GUIDE.md"
echo "按 Ctrl+C 退出"
echo "═══════════════════════════════════════════════════════════"
echo ""

# 启动 ollmcp 客户端
cd "${SCRIPT_DIR}"
python3 -m mcp_client_for_ollama.cli --servers-json "$CONFIG_FILE" --model "$MODEL"
