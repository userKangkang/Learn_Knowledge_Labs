import { useParams } from "react-router-dom";
import { GraphCanvas } from "../features/graph-editor/GraphCanvas";
import { TopBar } from "../features/graph-editor/TopBar";
import { useGraph } from "../features/graphs/hooks";

export function GraphEditorPage() {
  const { graphId = "" } = useParams();
  const { data, isLoading, error } = useGraph(graphId);

  if (isLoading) {
    return <div className="page">加载知识图…</div>;
  }

  if (error || !data) {
    return <div className="page error-text">知识图不存在或已删除。</div>;
  }

  return (
    <div className="editor-page">
      <TopBar title={data.title} />
      <GraphCanvas graphId={graphId} />
    </div>
  );
}
