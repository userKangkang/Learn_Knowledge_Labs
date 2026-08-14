import { useState } from "react";
import { Link } from "react-router-dom";
import { useEditorStore } from "./editorStore";
import { ModelSettingsDialog } from "./ModelSettingsDialog";

interface Props {
  title: string;
  graphId: string;
  onOpenPaperStudy: () => void;
}

export function TopBar({ title, graphId, onOpenPaperStudy }: Props) {
  const saveStatus = useEditorStore((s) => s.saveStatus);
  const selectedEdgeId = useEditorStore((s) => s.selectedEdgeId);
  const requestAddNode = useEditorStore((s) => s.requestAddNode);
  const requestEditSelectedEdge = useEditorStore((s) => s.requestEditSelectedEdge);
  const requestDeleteSelectedEdge = useEditorStore((s) => s.requestDeleteSelectedEdge);
  const [settingsOpen, setSettingsOpen] = useState(false);

  const statusText =
    saveStatus === "saving" ? "保存中…" : saveStatus === "saved" ? "已保存" : saveStatus === "error" ? "保存失败" : "就绪";

  return (
    <>
      <header className="topbar">
        <div className="topbar__left">
          <Link to="/" className="topbar__back">
            ← 图列表
          </Link>
          <h1>{title}</h1>
          <span className={`save-pill save-pill--${saveStatus}`}>{statusText}</span>
          <div className="topbar__tools">
            <button type="button" className="btn" onClick={() => requestAddNode()}>
              添加节点
            </button>
            <button type="button" className="btn btn--ghost" onClick={onOpenPaperStudy}>
              论文理解
            </button>
            <Link to={`/graphs/${graphId}/problem-map`} className="btn btn--ghost">
              论文-问题导图
            </Link>
            {selectedEdgeId && (
              <>
                <button type="button" className="btn btn--ghost" onClick={() => requestEditSelectedEdge()}>
                  更换类型
                </button>
                <button type="button" className="btn btn--ghost" onClick={() => requestDeleteSelectedEdge()}>
                  删除选中边
                </button>
              </>
            )}
          </div>
        </div>
        <button type="button" className="btn btn--ghost" onClick={() => setSettingsOpen(true)}>
          模型设置
        </button>
      </header>
      <ModelSettingsDialog open={settingsOpen} onClose={() => setSettingsOpen(false)} />
    </>
  );
}
