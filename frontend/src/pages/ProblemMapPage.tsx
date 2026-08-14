import { useState } from "react";
import { useParams } from "react-router-dom";
import { useGraph } from "../features/graphs/hooks";
import { PaperStudyDialog } from "../features/paper-study/PaperStudyDialog";
import { ProblemMapCanvas } from "../features/problem-map/ProblemMapWorkspace";

export function ProblemMapPage() {
  const { graphId = "" } = useParams();
  const { data, isLoading, error } = useGraph(graphId);
  const [paperStudy, setPaperStudy] = useState<{ open: boolean; studyId: string | null }>({
    open: false,
    studyId: null,
  });

  if (isLoading) {
    return <div className="page">加载论文-问题导图…</div>;
  }

  if (error || !data) {
    return <div className="page error-text">知识图不存在或已删除。</div>;
  }

  return (
    <div className="pm-page">
      <ProblemMapCanvas
        graphId={graphId}
        graphTitle={data.title}
        onOpenPaper={(studyId) => setPaperStudy({ open: true, studyId })}
      />
      <PaperStudyDialog
        open={paperStudy.open}
        graphId={graphId}
        initialStudyId={paperStudy.studyId ?? undefined}
        onClose={() => setPaperStudy({ open: false, studyId: null })}
      />
    </div>
  );
}
