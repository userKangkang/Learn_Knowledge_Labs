import { useEffect, useState } from "react";
import { EDGE_TYPES, EDGE_TYPE_LABELS, type EdgeType } from "../../entities/edge/types";

interface Props {
  open: boolean;
  mode?: "create" | "edit";
  initialType?: EdgeType;
  initialCustomLabel?: string | null;
  onCancel: () => void;
  onConfirm: (type: EdgeType, customLabel?: string) => void;
}

export function EdgeTypeDialog({
  open,
  mode = "create",
  initialType = "PREREQUISITE_OF",
  initialCustomLabel = "",
  onCancel,
  onConfirm,
}: Props) {
  const [type, setType] = useState<EdgeType>(initialType);
  const [customLabel, setCustomLabel] = useState(initialCustomLabel ?? "");

  useEffect(() => {
    if (!open) return;
    setType(initialType);
    setCustomLabel(initialCustomLabel ?? "");
  }, [open, initialType, initialCustomLabel]);

  if (!open) return null;

  const title = mode === "edit" ? "更换边类型" : "选择边类型";
  const confirmText = mode === "edit" ? "保存" : "创建边";

  return (
    <div className="modal-backdrop">
      <div className="modal">
        <h3>{title}</h3>
        <label>
          类型
          <select value={type} onChange={(e) => setType(e.target.value as EdgeType)}>
            {EDGE_TYPES.map((item) => (
              <option key={item} value={item}>
                {EDGE_TYPE_LABELS[item]}
              </option>
            ))}
          </select>
        </label>
        {type === "CUSTOM" && (
          <label>
            自定义标签
            <input
              value={customLabel}
              onChange={(e) => setCustomLabel(e.target.value)}
              placeholder="例如：类比于"
            />
          </label>
        )}
        <div className="modal__actions">
          <button type="button" className="btn btn--ghost" onClick={onCancel}>
            取消
          </button>
          <button
            type="button"
            className="btn"
            disabled={type === "CUSTOM" && !customLabel.trim()}
            onClick={() => onConfirm(type, customLabel.trim() || undefined)}
          >
            {confirmText}
          </button>
        </div>
      </div>
    </div>
  );
}
