import { useState } from "react";
import { useParams } from "react-router-dom";
import { GraphCanvas } from "../features/graph-editor/GraphCanvas";
import { TopBar } from "../features/graph-editor/TopBar";
import { useGraph } from "../features/graphs/hooks";
import { PaperStudyDialog } from "../features/paper-study/PaperStudyDialog";

export function GraphEditorPage() {
  const { graphId = "" } = useParams();
  const { data, isLoading, error } = useGraph(graphId);
  const [paperStudyOpen, setPaperStudyOpen] = useState(false);

  if (isLoading) {
    return <div className="page">加载知识图…</div>;
  }

  if (error || !data) {
    return <div className="page error-text">知识图不存在或已删除。</div>;
  }

  return (
    <div className="editor-page">
      <TopBar title={data.title} graphId={graphId} onOpenPaperStudy={() => setPaperStudyOpen(true)} />
      <GraphCanvas graphId={graphId} />
      <PaperStudyDialog
        open={paperStudyOpen}
        graphId={graphId}
        onClose={() => setPaperStudyOpen(false)}
      />
    </div>
  );
}
