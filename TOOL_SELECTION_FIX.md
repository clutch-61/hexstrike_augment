# 工具选择问题修复报告

## 问题描述

在多智能体系统(MA模式)测试中，发现以下两个关键问题：

### 问题1: Tool Selector 选择不相关的工具
**症状**: 
- Strategy Agent 指定关键词 `["curl", "actuator", "springboot"]`
- Tool Selector 却选择了完全不相关的 `hexstrike-ai.autorecon_scan`

**根本原因**:
- 关键词扩展字典中**缺少 curl、http、web 相关术语的映射**
- 关键词匹配评分逻辑不够精确，导致误匹配

### 问题2: Executor 使用错误的工具列表
**症状**:
- Tool Selector 选择了 `hexstrike-ai.http_framework_test`
- Executor 却收到了 `hexstrike-ai.nmap_scan` 等完全不同的工具
- 导致 Executor 将 `http_framework_test` 当作 nmap 的参数

**根本原因**:
- `context_manager.get_messages_for_agent()` 返回**所有历史消息**
- Coordinator 没有区分最新消息和历史消息
- Executor 收到的是**上一次迭代的工具列表**，而不是当前迭代的

## 修复方案

### 修复1: 增强关键词匹配 (selector_agent.py)

#### 1.1 扩展关键词字典
```python
# 新增 Web/HTTP 请求相关术语映射
'curl': ['http', 'request', 'web', 'get', 'post', 'api', 'endpoint', 'httpx'],
'http': ['curl', 'request', 'web', 'get', 'post', 'api', 'httpx', 'fetch'],
'request': ['curl', 'http', 'web', 'get', 'post', 'api', 'httpx'],
'web': ['http', 'curl', 'request', 'httpx', 'browser', 'url'],
'api': ['http', 'curl', 'request', 'endpoint', 'rest', 'httpx'],
'httpx': ['http', 'curl', 'request', 'probe', 'web'],
'actuator': ['springboot', 'spring', 'endpoint', 'http', 'api'],
'springboot': ['spring', 'actuator', 'java', 'web', 'http'],
```

#### 1.2 优化评分算法
```python
# 优先匹配工具名称中的精确关键词（最高优先级）
for term in search_terms:
    if term in tool_name_lower:
        score += 10  # 提高到10分

# 检查完整工具文本中的匹配
for term in expanded_terms:
    if term in tool_text:
        score += 5 if term in search_terms else 1  # 原始关键词5分，扩展词1分

# 多关键词匹配加成
match_count = sum(1 for term in search_terms if term in tool_text)
score += match_count * 3
```

#### 1.3 调整返回数量
- 从返回前30个工具降低到**前10个**，提高精确度

#### 1.4 添加调试日志
```python
self.log(f"Search terms: {', '.join(sorted(search_terms))}", "debug")
self.log(f"Top 5 matches by score:", "debug")
for tool, score in matched_tools[:5]:
    self.log(f"  {tool.name}: score={score}", "debug")
```

### 修复2: 修复消息传递问题

#### 2.1 添加 get_latest_message_for_agent() 方法 (context_manager.py)
```python
def get_latest_message_for_agent(self, agent_name: str, message_type: Optional[str] = None) -> Optional[AgentMessage]:
    """获取指定智能体的最新消息，可选按类型过滤"""
    matching_messages = [msg for msg in reversed(self.messages) 
                       if msg.to_agent == agent_name and 
                       (message_type is None or msg.message_type == message_type)]
    return matching_messages[0] if matching_messages else None
```

#### 2.2 更新 Coordinator 使用最新消息 (autonomous_coordinator.py)
```python
# 获取 Selector 的最新 tool_selection 消息
latest_msg = self.context_manager.get_latest_message_for_agent("ExecutorAgent", "tool_selection")

if not latest_msg:
    # 错误处理...
    
tool_objects = latest_msg.content.get("tool_objects", [])
```

#### 2.3 增强 Executor 调试和验证 (executor_agent.py)
```python
# 记录接收到的工具列表
self.log(f"Received {len(tool_objects)} tool objects from Selector", "debug")
self.log(f"Tools: {', '.join(tool_names[:5])}", "debug")

# 在 prompt 中明确列出可用工具
self.log(f"Selector provided tools: {', '.join(tool_names)}", "debug")

# 验证模型选择的工具是否在列表中
if tool_name not in tool_names:
    self.log(f"⚠ Model selected '{tool_name}' which is NOT in Selector's list!", "warning")
```

### 修复3: 其他优化

#### 3.1 调整最大迭代次数 (strategy_agent.py)
- 从 `MAX_ITERATIONS: 30` 降低到 `MAX_ITERATIONS: 15`
- 避免过度迭代

## 预期效果

1. **关键词匹配准确性提升**
   - curl/http 相关任务能正确匹配到 httpx_probe、http_framework_test 等工具
   - 避免选择无关的 autorecon_scan、zap_scan 等工具

2. **消息传递可靠性增强**
   - Executor 始终接收到**当前迭代**的最新工具列表
   - 消除历史消息干扰

3. **调试能力提升**
   - 完整的工具选择评分日志
   - 工具列表传递验证日志
   - 便于追踪和诊断问题

## 测试建议

使用相同的测试场景重新运行：
```bash
./start_with_multi_agent.sh
```

观察日志输出：
1. Tool Selector 的评分结果是否合理
2. Executor 收到的工具列表是否与 Selector 一致
3. 最终选择的工具是否符合任务需求

## 文件修改清单

- ✅ `mcp_client_for_ollama/multi_agent/selector_agent.py`
  - 扩展关键词字典（+11个新映射）
  - 优化评分算法
  - 添加调试日志

- ✅ `mcp_client_for_ollama/multi_agent/context_manager.py`
  - 新增 `get_latest_message_for_agent()` 方法

- ✅ `mcp_client_for_ollama/multi_agent/autonomous_coordinator.py`
  - 使用最新消息 API
  - 增强错误处理

- ✅ `mcp_client_for_ollama/multi_agent/executor_agent.py`
  - 添加工具列表接收日志
  - 添加工具选择验证
  - 改进 prompt 说明

- ✅ `mcp_client_for_ollama/multi_agent/strategy_agent.py`
  - 降低最大迭代次数

