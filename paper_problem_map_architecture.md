# 论文-问题导图：架构与实现规格

版本：0.1
目标读者：Coding Agent / 项目开发者

---

## 1. 项目定义

论文-问题导图是 Learn Knowledge Labs 的第三个模块：在**知识图**（概念怎么连）与**论文解读**（一篇论文读懂没有）之上，增加一个**跨论文的问题空间**，回答"这些论文之间靠什么问题连起来"。

核心思想：

1. 一篇论文解决的是若干**共享问题**下的子问题；多篇论文可能指向同一个共享问题；
2. 一个共享问题被越多论文指向，说明它在你阅读语料中的**覆盖度**越高（这是个人学习信号，不是领域客观重要度）；
3. 共享问题空间内部有层级：共性大问题会在不同场景/角度下分化为子场景子问题；
4. 论文侧的问题表述**直接复用论文解读模块的问题卡**（PaperProblemCard），不新建平行实体；
5. 论文-问题导图与知识图是**两套独立体系**，分别使用独立画布，通过显式关联建立联系。

核心原则（与知识图模块一致）：

- 图结构由用户控制；LLM 只能提议候选，不能直接建点连边；
- 论文侧子问题 = 问题卡，不重复创建；
- 覆盖度实时计算，不落冗余计数；
- 共享问题有层级，但不设"大问题/子问题"固定类型，层级由边决定；
- 所有实体软删除，删除前必须解除关联（与"有边节点不可删"一致）。

---

## 2. 数据模型

新增 4 张表（迁移 016）：

### 2.1 shared_problems（共享问题节点）

| 字段 | 说明 |
|------|------|
| id | 主键，uuid |
| graph_id | FK knowledge_graphs.id，按知识图隔离 |
| title | 问题标题 |
| description | 问题定性描述，可空 |
| created_at / updated_at | 时间戳 |
| deleted_at | 软删除 |

不设问题类型列：层级由 shared_problem_edges 决定，没有入边的节点即为共性大问题，渲染时放大显示。

### 2.2 shared_problem_edges（问题空间层级边）

| 字段 | 说明 |
|------|------|
| id | 主键 |
| graph_id | FK knowledge_graphs.id |
| source_problem_id | FK shared_problems.id，父问题 |
| target_problem_id | FK shared_problems.id，子问题 |
| relation_label | 默认 `SPECIALIZES_INTO`；允许自定义为"在低资源场景下"等场景/角度描述 |
| created_at / deleted_at | 时间戳 / 软删除 |

唯一约束 `(graph_id, source_problem_id, target_problem_id, relation_label)`；禁止自环；方向约定**父问题 → 子问题**（与知识图"父 → 子"一致）。

### 2.3 problem_card_links（论文侧 ↔ 共享侧桥接边）

| 字段 | 说明 |
|------|------|
| id | 主键 |
| graph_id | FK knowledge_graphs.id |
| problem_card_id | FK paper_problem_cards.id（复用问题卡） |
| shared_problem_id | FK shared_problems.id |
| link_type | `CORE`（核心解决）/ `TOUCHED`（顺带提及）；创建时默认取问题卡的 selected |
| created_at / updated_at / deleted_at | 时间戳 / 软删除 |

唯一约束 `(problem_card_id, shared_problem_id)`。多对多：一张卡可对应多个共享问题，一个共享问题可被多张卡指向。问题卡硬删除时，关联边随 ORM 级联一并删除。

### 2.4 problem_map_positions（画布位置）

| 字段 | 说明 |
|------|------|
| id | 主键 |
| graph_id | FK knowledge_graphs.id |
| entity_type | `PAPER`（指向 paper_studies）/ `PROBLEM`（指向 shared_problems） |
| entity_id | 对应实体 id |
| position_x / position_y | 画布坐标 |
| created_at / updated_at | 时间戳 |

唯一约束 `(graph_id, entity_type, entity_id)`。

---

## 3. 画布元素

论文-问题导图使用独立画布（独立路由），包含三类元素：

| 元素 | 来源 | 渲染 |
|------|------|------|
| 论文节点 | paper_studies | 矩形，点击跳回论文解读对话框 |
| 共享问题节点 | shared_problems | 圆形；无入边（根问题）放大；显示覆盖度徽标 |
| 问题层级边 | shared_problem_edges | 实线，标签为 relation_label |
| 论文 ↔ 问题关联边 | problem_card_links | 每条边代表一张问题卡，**标签为问题卡标题**；CORE 实线、TOUCHED 虚线 |

---

## 4. 覆盖度口径

对某个共享问题实时计算三个数字（均按 `distinct paper_studies.id` 去重）：

- `coverage_paper_count`：至少有一条关联的问题卡所属论文数；
- `coverage_core_count`：至少有一条 `CORE` 关联的问题卡所属论文数；
- `coverage_touched_count`：至少有一条 `TOUCHED` 关联的问题卡所属论文数。

一个论文可同时出现在 core 与 touched 中（一张卡 CORE、另一张卡 TOUCHED 指向同一问题）。这三个数在服务层单条聚合 SQL 中计算，不落冗余字段。

---

## 5. API

### 5.1 导图 bundle

```http
GET /api/v1/graphs/{graphId}/problem-map
```

返回画布一次性数据：`{ problems, edges, links, papers, positions }`。`papers` 为 `[{ study_id, title, cards: [{ id, title, selected }] }]`。

### 5.2 共享问题

```http
POST   /api/v1/graphs/{graphId}/problems
GET    /api/v1/graphs/{graphId}/problems
GET    /api/v1/problems/{problemId}
PATCH  /api/v1/problems/{problemId}
DELETE /api/v1/problems/{problemId}
```

删除规则：存在活跃层级边或关联边时禁止删除（返回 409），必须先解除关联。

### 5.3 问题层级边

```http
POST   /api/v1/graphs/{graphId}/problem-edges
GET    /api/v1/graphs/{graphId}/problem-edges
PATCH  /api/v1/problem-edges/{edgeId}
DELETE /api/v1/problem-edges/{edgeId}
```

PATCH 支持改 `relation_label` 与 `reverse`（反转方向）。

### 5.4 问题卡关联

```http
POST   /api/v1/problem-cards/{cardId}/links
GET    /api/v1/graphs/{graphId}/card-links
PATCH  /api/v1/card-links/{linkId}
DELETE /api/v1/card-links/{linkId}
```

### 5.5 位置持久化

```http
PUT /api/v1/graphs/{graphId}/problem-map/positions
```

请求体为位置列表，按 `(entity_type, entity_id)` 批量 upsert。

---

## 6. LLM 候选流程（Phase 3）

```http
POST /api/v1/graphs/{graphId}/problem-map/suggest
POST /api/v1/graphs/{graphId}/problem-map/apply
```

- `suggest` 输入：图内 `overview.user_status = CONFIRMED` 的论文的问题卡（标题 + 定性概述 + 专业性解读 + selected）；
- 输出：候选共享问题（标题/描述/建议挂到哪个已有问题下）与候选问题卡关联，**只存在于响应中，不落库**；
- `apply` 批量确认：由用户勾选的候选真正创建 shared_problems、shared_problem_edges 与 problem_card_links；
- LLM 不得直接写入数据库。

---

## 7. 前端（Phase 2）

- 新路由 `/graphs/:graphId/problem-map`，TopBar 在"知识图"与"论文-问题导图"间切换；
- 代码位于 `frontend/src/features/problem-map/`，复用 graph-editor 的 React Flow 画布模式；
- 问题节点显示覆盖度徽标（核心 x · 提及 y）；点击论文节点跳回 PaperStudyDialog；
- 右侧 Inspector：选中问题显示描述、覆盖度明细、关联论文与问题卡列表；选中论文显示其问题卡与已关联问题；
- 位置防抖持久化，照抄 knowledge_nodes 的做法；
- 画布边：问题层级边可编辑标签/反转/删除；论文↔问题边可切换 CORE/TOUCHED/删除。

---

## 8. 开发阶段

### Phase 1：数据层与 API

- 迁移 016：4 张新表；
- 模型、仓储、服务、Schema、API 路由；
- 图删除级联清理导图数据；
- 问题卡/论文删除时关联边随 ORM 级联清理；
- 单元/集成测试 `test_problem_map.py`。

验收：导图 CRUD 全部可用；覆盖度数字正确；删除保护生效；图删除后导图数据不可见。

### Phase 2：画布

- bundle 接口前端接入；React Flow 画布；位置持久化；覆盖度徽标；论文节点跳回解读对话框。

### Phase 3：LLM 候选

- suggest / apply 流程；候选侧栏；与概念地图 candidate → review → confirm 交互一致。

### Phase 4：打磨

- 空状态、错误状态、README 配图、演示截图。

---

## 9. 关键验收测试

1. 共享问题可创建/编辑/软删；有边或有关联时删除返回 409；
2. 层级边禁止自环、禁止同图重复；反转方向后端点互换；
3. 问题卡关联创建时默认 link_type 取自卡片的 selected；同卡同问题重复关联返回 409；
4. 覆盖度：两篇论文的问题卡（一 CORE 一 TOUCHED）指向同一问题 → paper=2、core=1、touched=1；
5. 位置批量 upsert 后 bundle 返回最新坐标；
6. 删除图后，问题/边/关联/位置均不可见；
7. 删除问题卡后，其关联边随卡片删除。

---

## 10. 与旧模块的关系

仓库中 008/009 迁移曾创建 `direction_workshops` / `problem_directions` / `learning_planning_papers` 等表，但**没有任何前后端代码**，属于废弃的方向工作坊模块。本模块明确不引用这些表；本地数据库中残留的表暂时原样保留，不做删除（如后续需要清理，另写独立迁移）。
