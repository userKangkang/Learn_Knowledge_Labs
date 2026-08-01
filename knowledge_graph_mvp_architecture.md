# 个人知识图学习应用：MVP 架构与实现规格

版本：0.1  
目标读者：Cursor Agent / Coding Agent / 项目开发者

---

## 1. 项目定义

本项目是一个**由用户手动构建知识结构、以节点级 LLM 对话为核心工作区的个人知识图应用**。

系统不负责自动生成整张知识图，也不负责替用户规划学习路径。用户主动创建节点、连接节点并选择边类型；LLM 仅在用户选中的当前节点内回答问题。系统负责：

1. 管理知识图、节点和带语义的边；
2. 为每个节点提供相互隔离的 LLM 对话空间；
3. 按用户配置，从指定父节点继承摘要或部分对话上下文；
4. 持久化节点摘要、完整问答、上下文策略和上下文快照；
5. 提供所有核心对象的增删改查和版本追踪。

核心原则：

- 图结构由用户控制；
- 节点对话默认隔离；
- 祖先上下文显式继承；
- 兄弟节点默认不共享上下文；
- 每次 LLM 请求的实际上下文必须可追溯；
- 所有问答、摘要和修改历史必须持久化。

---

## 2. MVP 范围

### 2.1 必须实现

1. 创建、重命名、删除知识图；
2. 手动创建、编辑、移动、删除节点；
3. 手动创建、编辑、删除带类型的边；
4. 每个节点拥有独立的节点详情和多个对话会话；
5. 每个节点可以配置从哪些父节点继承上下文；
6. 上下文可按“仅摘要、最近 N 轮、选择消息、完整会话”继承；
7. 兄弟节点和无关分支默认隔离；
8. 节点内调用 LLM API，支持流式输出；
9. 保存完整消息、消息版本、节点摘要版本；
10. 点击节点展开摘要；点击“查看对话”在侧边栏展开完整会话；
11. 所有图、节点、边、会话、消息、摘要、上下文策略均支持 CRUD；
12. 每次 LLM 调用保存不可变的上下文快照；
13. 页面刷新或应用重启后，图布局和所有数据仍然存在。

### 2.2 MVP 明确不做

1. 不自动生成整张知识图；
2. 不自动创建、删除或连接节点；
3. 不自动判断用户是否掌握知识；
4. 不做自动学习路径推荐；
5. 不做 CVT、SEVT、SRL 等心理模型；
6. 不做间隔复习；
7. 不做多人协作；
8. 不做全局知识库 RAG；
9. 不默认将整个知识图发送给 LLM；
10. 不默认跨兄弟节点或跨分支共享上下文。

LLM 可以在回答中提出“后续值得了解的问题”，但只能作为文本建议，不能自动变成图节点。

---

## 3. 推荐技术栈

以下为默认方案，可在项目已有技术栈明确后替换，但不应改变领域模型和接口语义。

### 3.1 前端

- React + TypeScript + Vite
- React Flow：知识图编辑器
- Zustand：本地 UI 状态
- TanStack Query：服务端状态、缓存和请求管理
- React Router：页面路由
- Markdown 渲染器：展示 LLM 回答和节点摘要
- SSE：接收流式 LLM 输出

### 3.2 后端

- FastAPI
- SQLAlchemy 2.x
- Alembic
- Pydantic v2
- SQLite：MVP 默认数据库
- PostgreSQL：后续部署可替换

### 3.3 LLM 网关

- 采用 OpenAI-compatible API 抽象；
- API Key 只能存在后端环境变量或安全配置中，不能暴露给浏览器；
- 支持 provider、base_url、model、temperature 等配置；
- LLM 请求通过统一网关执行，禁止前端直接请求模型提供商。

---

## 4. 总体架构

```text
┌──────────────────────────────────────────────┐
│                  Web Client                  │
│                                              │
│  GraphEditor   NodeInspector   ChatSidebar   │
│  ContextEditor SummaryPanel    HistoryPanel  │
└──────────────────────┬───────────────────────┘
                       │ REST + SSE
┌──────────────────────▼───────────────────────┐
│                Application API               │
│                                              │
│ GraphService       NodeService               │
│ EdgeService        ConversationService       │
│ SummaryService     ContextPolicyService      │
│ ContextBuilder     LLMGateway                │
└──────────────────────┬───────────────────────┘
                       │
┌──────────────────────▼───────────────────────┐
│                 Persistence                  │
│                                              │
│ Graph / Node / Edge                          │
│ Session / Message / Revision                 │
│ SummaryVersion / ContextPolicy               │
│ ContextSnapshot / LLMRequest                 │
└──────────────────────────────────────────────┘
```

---

## 5. 核心领域规则

以下规则必须写入代码注释、服务校验和自动化测试。

### 5.1 图结构规则

1. 节点和边只能由用户显式创建、修改或删除；
2. LLM 不得直接修改图结构；
3. 图底层使用有向多图模型：允许一个节点拥有多个入边和多个父节点；
4. 禁止 sourceNodeId 与 targetNodeId 相同；
5. 同一对节点允许存在不同类型的边；
6. 是否禁止同类型重复边，由数据库唯一约束决定，MVP 建议禁止。

### 5.2 上下文规则

1. 图边和上下文继承是两个独立概念；
2. 存在图边不代表自动继承对方内容；
3. 当前节点的当前会话默认进入上下文；
4. 其他节点只有被上下文策略显式选择后才能进入；
5. 兄弟节点默认不进入上下文；
6. 不允许默认加载整张图；
7. 每次请求必须保存实际发送给 LLM 的上下文快照；
8. 后续修改父节点摘要或历史消息，不得改变既有快照。

### 5.3 消息和摘要规则

1. 节点允许拥有多个对话会话；
2. 编辑消息不得覆盖原版本，必须生成 revision；
3. 删除消息默认软删除；
4. 修改历史消息后，需要标记其后续回答和引用摘要为“可能过期”；
5. 节点只有一个当前摘要，但必须保存摘要历史版本；
6. LLM 回答完成后不得自动覆盖节点摘要；
7. 摘要更新必须由用户点击触发并确认保存。

---

## 6. 初版边类型

```typescript
type EdgeType =
  | "IS_A"               // A 是 B 的一种
  | "PART_OF"            // A 是 B 的组成部分
  | "PREREQUISITE_OF"    // 理解 A 是理解 B 的前置
  | "EXAMPLE_OF"         // A 是 B 的示例
  | "CAUSES_OR_LEADS_TO" // A 导致或促进 B
  | "CONTRASTS_WITH"     // A 与 B 对比
  | "APPLIES_TO"         // A 应用于 B
  | "CUSTOM";            // 用户自定义关系
```

方向约定：

```text
A --PREREQUISITE_OF--> B
```

表示先理解 A，再理解 B。

CUSTOM 边必须提供 `customLabel`。

---

## 7. 领域模型

### 7.1 KnowledgeGraph

```typescript
interface KnowledgeGraph {
  id: string;
  title: string;
  description?: string;
  createdAt: string;
  updatedAt: string;
  deletedAt?: string;
}
```

### 7.2 KnowledgeNode

```typescript
interface KnowledgeNode {
  id: string;
  graphId: string;
  title: string;
  nodeType:
    | "TOPIC"
    | "CONCEPT"
    | "THEORY"
    | "METHOD"
    | "QUESTION"
    | "EXAMPLE"
    | "APPLICATION";
  positionX: number;
  positionY: number;
  currentSummaryVersionId?: string;
  createdAt: string;
  updatedAt: string;
  deletedAt?: string;
}
```

### 7.3 KnowledgeEdge

```typescript
interface KnowledgeEdge {
  id: string;
  graphId: string;
  sourceNodeId: string;
  targetNodeId: string;
  type: EdgeType;
  customLabel?: string;
  createdAt: string;
  updatedAt: string;
  deletedAt?: string;
}
```

### 7.4 ConversationSession

```typescript
interface ConversationSession {
  id: string;
  nodeId: string;
  title: string;
  createdAt: string;
  updatedAt: string;
  deletedAt?: string;
}
```

### 7.5 ChatMessage

```typescript
interface ChatMessage {
  id: string;
  sessionId: string;
  role: "USER" | "ASSISTANT" | "SYSTEM";
  content: string;
  status: "ACTIVE" | "EDITED" | "DELETED";
  currentRevision: number;
  llmRequestId?: string;
  createdAt: string;
  updatedAt: string;
}
```

### 7.6 MessageRevision

```typescript
interface MessageRevision {
  id: string;
  messageId: string;
  revisionNumber: number;
  content: string;
  createdAt: string;
}
```

### 7.7 NodeSummaryVersion

```typescript
interface NodeSummaryVersion {
  id: string;
  nodeId: string;
  versionNumber: number;
  content: string;
  authorType: "USER" | "LLM" | "LLM_AND_USER";
  generatedFromMessageIds: string[];
  createdAt: string;
}
```

### 7.8 NodeContextPolicy

```typescript
interface NodeContextPolicy {
  id: string;
  nodeId: string;
  includeCurrentNodeSummary: boolean;
  includeCurrentSessionHistory: boolean;
  maxContextTokens?: number;
  createdAt: string;
  updatedAt: string;
}
```

### 7.9 ContextSourceRule

每个被继承的父节点使用一条规则。

```typescript
interface ContextSourceRule {
  id: string;
  contextPolicyId: string;
  sourceNodeId: string;
  sourceSessionId?: string;
  includeSummary: boolean;
  conversationMode:
    | "NONE"
    | "LAST_N_TURNS"
    | "SELECTED_MESSAGES"
    | "FULL_SESSION";
  lastNTurns?: number;
  selectedMessageIds?: string[];
  orderIndex: number;
}
```

约束：

- `LAST_N_TURNS` 必须提供 `lastNTurns`；
- `SELECTED_MESSAGES` 必须提供 `selectedMessageIds`；
- `FULL_SESSION` 必须提供 `sourceSessionId`；
- MVP UI 默认仅允许从当前节点的直接父节点中选择来源；
- 后端仍须验证来源节点属于同一知识图。

### 7.10 ContextSnapshot

```typescript
interface ContextSnapshot {
  id: string;
  nodeId: string;
  sessionId: string;
  policyVersion: number;
  renderedSystemPrompt: string;
  renderedContext: string;
  estimatedInputTokens: number;
  createdAt: string;
}
```

### 7.11 ContextSnapshotItem

```typescript
interface ContextSnapshotItem {
  id: string;
  snapshotId: string;
  sourceNodeId?: string;
  sourceSessionId?: string;
  sourceType:
    | "CURRENT_NODE_SUMMARY"
    | "PARENT_NODE_SUMMARY"
    | "CURRENT_SESSION_MESSAGE"
    | "PARENT_SESSION_MESSAGE";
  sourceEntityId: string;
  sourceVersion: number;
  renderedContent: string;
  orderIndex: number;
}
```

### 7.12 LLMRequest

```typescript
interface LLMRequest {
  id: string;
  nodeId: string;
  sessionId: string;
  userMessageId: string;
  assistantMessageId?: string;
  contextSnapshotId: string;
  provider: string;
  model: string;
  status: "PENDING" | "STREAMING" | "SUCCEEDED" | "FAILED" | "CANCELLED";
  inputTokens?: number;
  outputTokens?: number;
  errorCode?: string;
  errorMessage?: string;
  createdAt: string;
  completedAt?: string;
}
```

---

## 8. 数据库表

MVP 至少包含：

```text
knowledge_graphs
knowledge_nodes
knowledge_edges
conversation_sessions
chat_messages
message_revisions
node_summary_versions
node_context_policies
context_source_rules
context_snapshots
context_snapshot_items
llm_requests
```

关键索引和约束：

1. `knowledge_nodes(graph_id)`；
2. `knowledge_edges(graph_id, source_node_id, target_node_id)`；
3. 唯一约束：`(graph_id, source_node_id, target_node_id, type)`；
4. `conversation_sessions(node_id)`；
5. `chat_messages(session_id, created_at)`；
6. 唯一约束：`message_revisions(message_id, revision_number)`；
7. 唯一约束：`node_summary_versions(node_id, version_number)`；
8. `context_source_rules(context_policy_id, order_index)`；
9. `context_snapshot_items(snapshot_id, order_index)`；
10. 所有主实体支持 `deleted_at` 软删除。

---

## 9. 上下文构建算法

### 9.1 输入

```typescript
interface BuildContextInput {
  nodeId: string;
  sessionId: string;
  newUserMessage: string;
}
```

### 9.2 固定顺序

上下文必须按确定性顺序构建：

1. 系统提示词；
2. 当前节点标题和类型；
3. 当前节点摘要（若启用）；
4. 按 `orderIndex` 排序的父节点摘要；
5. 按 `orderIndex` 排序的父节点选定对话；
6. 当前会话历史；
7. 当前用户新问题。

### 9.3 伪代码

```typescript
async function buildContext(input: BuildContextInput): Promise<ContextSnapshot> {
  const node = await nodeRepo.getRequired(input.nodeId);
  const session = await sessionRepo.getRequired(input.sessionId);
  assert(session.nodeId === node.id);

  const policy = await contextPolicyRepo.getOrCreateDefault(node.id);
  const rules = await contextRuleRepo.listOrdered(policy.id);

  const items: SnapshotItemDraft[] = [];

  if (policy.includeCurrentNodeSummary) {
    const summary = await summaryRepo.getCurrent(node.id);
    if (summary) items.push(renderCurrentNodeSummary(summary));
  }

  for (const rule of rules) {
    validateContextSourceRule(node.graphId, rule);

    if (rule.includeSummary) {
      const summary = await summaryRepo.getCurrent(rule.sourceNodeId);
      if (summary) items.push(renderParentSummary(summary, rule.orderIndex));
    }

    items.push(...await resolveConversationItems(rule));
  }

  if (policy.includeCurrentSessionHistory) {
    const messages = await messageRepo.listActive(session.id);
    items.push(...renderCurrentSession(messages));
  }

  const rendered = renderPrompt(node, items, input.newUserMessage);
  const budgeted = applyTokenBudget(rendered, policy.maxContextTokens);

  return snapshotRepo.createImmutable(budgeted);
}
```

### 9.4 Token 预算规则

MVP 使用确定性裁剪，不实现复杂语义压缩。

保留优先级：

```text
系统提示词
> 当前用户问题
> 当前节点摘要
> 父节点摘要
> 当前会话最近消息
> 父节点历史消息
> 当前会话较早消息
```

发生裁剪时：

1. 不得无提示地删除当前用户问题；
2. 不得修改已保存快照；
3. 前端显示“部分历史因上下文长度被省略”；
4. 快照中记录实际保留的内容。

---

## 10. LLM 调用流程

```text
用户在节点会话输入问题
        ↓
保存 USER 消息
        ↓
ContextBuilder 生成不可变快照
        ↓
创建 LLMRequest(PENDING)
        ↓
创建占位 ASSISTANT 消息
        ↓
调用 LLMGateway，SSE 流式返回
        ↓
持续更新前端显示
        ↓
结束后一次性提交最终 ASSISTANT 消息内容
        ↓
LLMRequest 标记 SUCCEEDED
```

失败处理：

- 请求失败时保留用户消息和失败记录；
- 占位 assistant 消息标记失败或删除；
- “重新生成”必须创建新的 LLMRequest 和新的 assistant 消息；
- 重试不得覆盖旧请求；
- 用户取消时标记 `CANCELLED`。

---

## 11. API 设计

### 11.1 Graph

```http
POST   /api/v1/graphs
GET    /api/v1/graphs
GET    /api/v1/graphs/{graphId}
PATCH  /api/v1/graphs/{graphId}
DELETE /api/v1/graphs/{graphId}
```

### 11.2 Node

```http
POST   /api/v1/graphs/{graphId}/nodes
GET    /api/v1/graphs/{graphId}/nodes
GET    /api/v1/nodes/{nodeId}
PATCH  /api/v1/nodes/{nodeId}
DELETE /api/v1/nodes/{nodeId}
PATCH  /api/v1/nodes/{nodeId}/position
```

### 11.3 Edge

```http
POST   /api/v1/graphs/{graphId}/edges
GET    /api/v1/graphs/{graphId}/edges
PATCH  /api/v1/edges/{edgeId}
DELETE /api/v1/edges/{edgeId}
```

### 11.4 Session

```http
POST   /api/v1/nodes/{nodeId}/sessions
GET    /api/v1/nodes/{nodeId}/sessions
PATCH  /api/v1/sessions/{sessionId}
DELETE /api/v1/sessions/{sessionId}
```

### 11.5 Message

```http
GET    /api/v1/sessions/{sessionId}/messages
PATCH  /api/v1/messages/{messageId}
DELETE /api/v1/messages/{messageId}
GET    /api/v1/messages/{messageId}/revisions
```

### 11.6 Summary

```http
GET    /api/v1/nodes/{nodeId}/summary
POST   /api/v1/nodes/{nodeId}/summary/generate
POST   /api/v1/nodes/{nodeId}/summary
GET    /api/v1/nodes/{nodeId}/summary/versions
POST   /api/v1/nodes/{nodeId}/summary/versions/{versionId}/activate
```

### 11.7 Context Policy

```http
GET    /api/v1/nodes/{nodeId}/context-policy
PUT    /api/v1/nodes/{nodeId}/context-policy
POST   /api/v1/nodes/{nodeId}/context-policy/sources
PATCH  /api/v1/context-sources/{sourceRuleId}
DELETE /api/v1/context-sources/{sourceRuleId}
POST   /api/v1/nodes/{nodeId}/context-preview
```

`context-preview` 返回即将发送的上下文，但不创建 LLM 请求。

### 11.8 Chat / LLM

```http
POST /api/v1/sessions/{sessionId}/messages/stream
```

请求：

```json
{
  "content": "请解释这个知识点",
  "model": "gpt-5.6",
  "temperature": 0.2
}
```

SSE 事件建议：

```text
request_created
context_built
delta
completed
failed
cancelled
```

---

## 12. 前端布局

```text
┌─────────────────────────────────────────────────────────────┐
│ 顶部栏：图名称 / 保存状态 / 模型设置                         │
├──────────────────────────────────┬──────────────────────────┤
│                                  │ 节点详情侧栏             │
│                                  │                          │
│          知识图画布              │ 标题 / 类型              │
│          React Flow              │ 当前摘要                 │
│                                  │ [编辑] [历史版本]        │
│                                  │                          │
│                                  │ 上下文继承设置           │
│                                  │ 会话列表                 │
│                                  │ [展开当前会话]           │
├──────────────────────────────────┴──────────────────────────┤
│ 可选底部/右侧 Chat Drawer：完整 LLM 对话                    │
└─────────────────────────────────────────────────────────────┘
```

交互要求：

1. 单击节点：打开节点详情；
2. 节点卡可展开或收起摘要；
3. 点击“查看对话”：打开 Chat Drawer；
4. 拖动节点结束后持久化位置；
5. 连接两个节点后弹出边类型选择；
6. 编辑上下文策略时显示 token 预估和上下文预览；
7. 当前 LLM 流式回答不阻塞图编辑；
8. 页面离开前，未保存编辑应提示。

---

## 13. 后端模块划分

```text
app/
├── api/
│   ├── graphs.py
│   ├── nodes.py
│   ├── edges.py
│   ├── sessions.py
│   ├── messages.py
│   ├── summaries.py
│   ├── contexts.py
│   └── llm.py
├── domain/
│   ├── graph/
│   ├── conversation/
│   ├── summary/
│   ├── context/
│   └── llm/
├── services/
│   ├── graph_service.py
│   ├── node_service.py
│   ├── edge_service.py
│   ├── conversation_service.py
│   ├── summary_service.py
│   ├── context_policy_service.py
│   ├── context_builder.py
│   └── llm_gateway.py
├── repositories/
├── db/
├── schemas/
├── prompts/
├── tests/
└── main.py
```

前端建议：

```text
src/
├── app/
├── pages/
├── features/
│   ├── graphs/
│   ├── graph-editor/
│   ├── node-inspector/
│   ├── conversations/
│   ├── summaries/
│   ├── context-policy/
│   └── llm-settings/
├── entities/
│   ├── graph/
│   ├── node/
│   ├── edge/
│   ├── session/
│   └── message/
├── shared/
└── main.tsx
```

---

## 14. 开发阶段

### Phase 0：项目骨架

- 初始化前后端；
- 数据库连接和迁移；
- 统一错误响应；
- OpenAPI 文档；
- 基础测试框架。

验收：前后端可启动，健康检查通过，迁移可执行。

### Phase 1：图、节点、边 CRUD

- 图列表；
- React Flow 画布；
- 节点和边 CRUD；
- 节点位置持久化；
- 边类型选择。

验收：刷新页面后图结构和布局不丢失。

### Phase 2：节点详情、摘要和会话

- 节点详情侧栏；
- 节点摘要 CRUD 和版本；
- 一个节点多个会话；
- 消息列表和消息 CRUD。

验收：不同节点和不同会话的消息严格隔离。

### Phase 3：上下文策略

- 父节点上下文选择；
- 摘要、最近 N 轮、指定消息、完整会话；
- 上下文预览；
- 兄弟节点默认隔离；
- ContextSnapshot 持久化。

验收：预览内容与实际快照完全一致。

### Phase 4：LLM 网关

- OpenAI-compatible provider；
- SSE 流式响应；
- LLMRequest 状态；
- 失败、重试、取消；
- token 统计。

验收：每个回答都能追溯到消息、请求和上下文快照。

### Phase 5：摘要生成和版本一致性

- 从选定消息生成摘要候选；
- 用户确认后保存；
- 编辑历史消息时标记相关摘要可能过期；
- 摘要版本切换。

验收：自动生成不会未经确认覆盖当前摘要。

### Phase 6：稳定性与体验

- 空状态；
- 加载和错误状态；
- 并发保存防抖；
- 数据导出；
- 单元测试、集成测试、端到端测试。

---

## 15. 关键验收测试

### 15.1 图结构

- 用户可以手动创建和删除节点；
- LLM 回答不能自动创建节点；
- 相同节点之间可以创建不同类型边；
- 禁止自环；
- 软删除后默认查询不可见。

### 15.2 上下文隔离

给定：

```text
Root
├── Node A
└── Node B
```

Node A 有对话“A-specific”。在 Node B 发起请求时：

- 默认上下文不得出现“A-specific”；
- 即使 Node A 和 Node B 拥有共同父节点，也不得共享；
- 只有显式把 Node A 加入来源后才能出现。

### 15.3 父节点继承

- 选择“仅摘要”时，不得包含父节点完整对话；
- 选择“最近 2 轮”时，只包含最后 2 个 user-assistant turn；
- 选择消息时，只包含指定 messageId；
- 父节点后续修改不改变旧 ContextSnapshot。

### 15.4 消息版本

- 编辑消息后保留旧 revision；
- 旧 ContextSnapshot 仍引用旧 revision；
- 新请求使用当前 revision；
- 删除消息不会破坏旧快照。

### 15.5 摘要

- 节点可无摘要；
- 生成摘要只产生候选；
- 用户确认后生成新版本；
- 可以查看和切换历史版本；
- 编辑源消息后，相关摘要显示“可能过期”。

### 15.6 持久化

- 页面刷新后保留节点位置；
- 服务重启后保留图、会话和消息；
- LLM 请求失败后仍保留失败记录；
- 重试产生新请求，不覆盖旧记录。

---

## 16. Cursor Agent 执行规则

不要要求 Agent 一次性实现整个项目。每一阶段都按以下流程执行：

1. 先检查现有仓库结构和依赖；
2. 输出当前阶段的文件修改计划；
3. 明确将新增或修改的数据库表、接口和组件；
4. 只实现当前阶段；
5. 运行 lint、类型检查、单元测试和相关集成测试；
6. 汇报完成项、未完成项和已知风险；
7. 不擅自扩大功能范围；
8. 不引入自动图生成、自动学习规划或心理模型。

---

## 17. 可直接发送给 Cursor Agent 的首轮提示词

```text
你需要在当前仓库中实现一个“用户手动构建的个人知识图学习应用”。

请先阅读仓库，不要立即修改代码。先输出：
1. 当前技术栈、目录结构和已有能力；
2. 与下面规格的差距；
3. 分阶段实现计划；
4. Phase 0 和 Phase 1 将新增或修改的文件；
5. 数据库迁移计划；
6. 主要风险和需要我确认的问题。

核心产品规则：
- 图结构必须由用户手动创建，LLM 不得自动创建、删除或连接节点；
- 图是有向带类型多图，不是严格树；
- 每个节点拥有独立摘要和多个独立 LLM 对话会话；
- 当前节点可显式继承指定父节点的摘要或部分对话；
- 兄弟节点和无关分支默认隔离；
- 图边与上下文继承是两个独立系统；
- 每次 LLM 调用必须保存不可变上下文快照；
- 消息和摘要必须支持版本追踪，删除默认软删除；
- 所有数据必须持久化。

第一轮只实施 Phase 0 和 Phase 1：
- 项目骨架、数据库迁移、统一错误处理、测试框架；
- KnowledgeGraph、KnowledgeNode、KnowledgeEdge 的模型与 CRUD；
- React Flow 图编辑器；
- 节点创建、编辑、删除、拖动和位置持久化；
- 边创建、编辑、删除和类型选择；
- 页面刷新后完整恢复图和布局。

不要实现：
- LLM 调用；
- 节点对话；
- 上下文继承；
- 自动摘要；
- 自动图生成；
- 学习路线推荐；
- 心理学模块。

在我批准计划前不要开始大规模编码。
```

---

## 18. MVP 完成定义

当且仅当满足以下条件时，MVP 可视为完成：

1. 用户可以完全手动维护知识图；
2. 每个节点可以拥有摘要和多个独立对话；
3. 用户可以精确选择父节点的哪些内容进入当前节点上下文；
4. 兄弟节点默认隔离；
5. 所有 LLM 请求均可追溯到不可变上下文快照；
6. 所有问答、摘要、图结构和布局均持久化；
7. 消息和摘要的编辑不会破坏历史可追溯性；
8. LLM 不会擅自改变图结构。

