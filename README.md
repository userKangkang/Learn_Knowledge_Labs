# Knowledge Labs

个人知识图学习应用：用户手动构建有向带类型知识图，并在节点内与 LLM 对话学习。

## 技术栈

- 后端：FastAPI + SQLAlchemy 2 + Alembic + SQLite（`uv`）
- 前端：React + TypeScript + Vite + React Flow + Zustand + TanStack Query（`pnpm`）
- LLM：DeepSeek `deepseek-v4-pro`（OpenAI 兼容，服务端网关 + SSE）

## 快速开始

### 后端

```bash
cd backend
uv sync
cp .env.example .env   # 填入 DEEPSEEK_API_KEY
uv run alembic upgrade head
uv run uvicorn app.main:app --reload --port 8000
```

- API：http://127.0.0.1:8000/api/v1/health
- OpenAPI：http://127.0.0.1:8000/docs

环境变量见 `backend/.env.example`（也兼容 `DEEPSEEK_API`）。

### 前端

```bash
cd frontend
pnpm install
pnpm dev
```

打开 http://127.0.0.1:5173

### 测试

```bash
cd backend
uv run pytest
```

## Phase 0–4 已实现

- 图 / 节点 / 边 CRUD（软删除）
- 有边节点禁止删除（HTTP 409）
- 删图级联软删节点、边、摘要、会话、上下文策略与消息
- React Flow 空画布编辑、边/节点类型中文展示、位置防抖持久化
- 节点摘要版本（手写确认保存 / 激活切换 / 软删 / 原地修改）
- 一节点多会话；消息编辑 revision、软删
- 上下文继承（按会话）：当前会话历史始终带上；本节点摘要可选；同节点其他会话不限；前 3 代祖先不限；非祖先最多 2 节点；预览与快照
- Chat Drawer：SSE 流式对话、取消、LLMRequest + 上下文快照追溯
- 纯文字可选 `deepseek-v4-pro` / `kimi-k2.6`；联网仅 DeepSeek flash+search
- 有图/PDF 附件时强制 `kimi-k2.6` 做详细文字摘要（便于跨厂商续聊只带正文）
- 跨厂商历史只保留最终正文；同厂商可附带 vendor 细节
- 模型设置只读面板（Key 仅服务端：`DEEPSEEK_API_KEY` / `MOONSHOT_API_KEY`）

## 明确未实现

摘要自动生成、图片/多模态视觉、自动建图。
