import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useCreateGraph, useDeleteGraph, useGraphs, useUpdateGraph } from "../features/graphs/hooks";
import { confirmDialog, promptDialog } from "../shared/ui/dialogStore";

export function GraphListPage() {
  const navigate = useNavigate();
  const { data, isLoading, error } = useGraphs();
  const createGraph = useCreateGraph();
  const updateGraph = useUpdateGraph();
  const deleteGraph = useDeleteGraph();
  const [title, setTitle] = useState("未命名知识图");

  return (
    <div className="page">
      <header className="page-header">
        <div>
          <p className="eyebrow">Knowledge Labs</p>
          <h1>我的知识图</h1>
          <p className="muted">手动构建节点与带类型的边。新建图从空画布开始。</p>
        </div>
      </header>

      <section className="card-panel">
        <h2>新建知识图</h2>
        <div className="inline-form">
          <input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="图标题" />
          <button
            type="button"
            className="btn"
            disabled={!title.trim() || createGraph.isPending}
            onClick={async () => {
              const graph = await createGraph.mutateAsync({ title: title.trim() });
              navigate(`/graphs/${graph.id}`);
            }}
          >
            创建并打开
          </button>
        </div>
      </section>

      <section className="card-panel">
        <h2>图列表</h2>
        {isLoading && <p className="muted">加载中…</p>}
        {error && <p className="error-text">加载失败</p>}
        {!isLoading && (data?.length ?? 0) === 0 && <p className="muted">还没有知识图，先创建一张空图吧。</p>}
        <ul className="graph-list">
          {data?.map((graph) => (
            <li key={graph.id} className="graph-list__item">
              <div>
                <Link to={`/graphs/${graph.id}`} className="graph-list__title">
                  {graph.title}
                </Link>
                <p className="muted">更新于 {new Date(graph.updated_at).toLocaleString()}</p>
              </div>
              <div className="graph-list__actions">
                <button
                  type="button"
                  className="btn btn--ghost"
                  onClick={async () => {
                    const next = await promptDialog({
                      title: "重命名知识图",
                      label: "图标题",
                      defaultValue: graph.title,
                      confirmLabel: "保存",
                    });
                    if (!next) return;
                    await updateGraph.mutateAsync({ graphId: graph.id, title: next });
                  }}
                >
                  重命名
                </button>
                <button
                  type="button"
                  className="btn btn--danger"
                  onClick={async () => {
                    const ok = await confirmDialog({
                      title: "删除知识图",
                      description: `确认删除「${graph.title}」？其下节点、边、摘要与会话将一并软删除。`,
                      confirmLabel: "删除",
                      tone: "danger",
                    });
                    if (!ok) return;
                    await deleteGraph.mutateAsync(graph.id);
                  }}
                >
                  删除
                </button>
              </div>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}
