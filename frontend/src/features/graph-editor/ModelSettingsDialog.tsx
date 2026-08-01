import { useQuery } from "@tanstack/react-query";
import { getLlmSettings } from "../conversations/api";

interface Props {
  open: boolean;
  onClose: () => void;
}

export function ModelSettingsDialog({ open, onClose }: Props) {
  const query = useQuery({
    queryKey: ["llm", "settings"],
    queryFn: getLlmSettings,
    enabled: open,
  });

  if (!open) return null;

  const data = query.data;

  return (
    <div className="modal-backdrop app-dialog-backdrop" role="presentation" onClick={onClose}>
      <div
        className="modal app-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="model-settings-title"
        onClick={(e) => e.stopPropagation()}
      >
        <h2 id="model-settings-title">模型设置</h2>
        {query.isLoading && <p className="muted">加载中…</p>}
        {query.error && <p className="error-text">{(query.error as Error).message}</p>}
        {data && (
          <dl className="settings-dl">
            <div>
              <dt>纯文字可选</dt>
              <dd>
                {data.model} / {data.kimi_model}
              </dd>
            </div>
            <div>
              <dt>多模态/附件</dt>
              <dd>强制 {data.kimi_model}（详细文字摘要）</dd>
            </div>
            <div>
              <dt>联网</dt>
              <dd>{data.search_model} + thinking + search</dd>
            </div>
            <div>
              <dt>DeepSeek Key</dt>
              <dd>{data.api_key_configured ? "已配置" : "未配置"}</dd>
            </div>
            <div>
              <dt>Kimi Key</dt>
              <dd>{data.kimi_api_key_configured ? "已配置" : "未配置（MOONSHOT_API_KEY）"}</dd>
            </div>
            <div>
              <dt>DeepSeek URL</dt>
              <dd>{data.base_url}</dd>
            </div>
            <div>
              <dt>Moonshot URL</dt>
              <dd>{data.moonshot_base_url}</dd>
            </div>
          </dl>
        )}
        <p className="app-dialog__desc">
          跨厂商续聊只保留最终正文；有附件时请用短指令，让本轮专注文件解析。
        </p>
        <div className="modal__actions">
          <button type="button" className="btn" onClick={onClose}>
            关闭
          </button>
        </div>
      </div>
    </div>
  );
}
