import { useEffect, useId, useRef, useState } from "react";
import { useDialogStore } from "./dialogStore";

export function AppDialog() {
  const dialog = useDialogStore((s) => s.dialog);
  const close = useDialogStore((s) => s.close);
  const [promptValue, setPromptValue] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);
  const titleId = useId();

  useEffect(() => {
    if (!dialog) return;
    if (dialog.kind === "prompt") {
      setPromptValue(dialog.options.defaultValue);
      const timer = window.setTimeout(() => inputRef.current?.focus(), 0);
      return () => window.clearTimeout(timer);
    }
  }, [dialog]);

  useEffect(() => {
    if (!dialog) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key !== "Escape") return;
      event.preventDefault();
      if (dialog.kind === "confirm") dialog.resolve(false);
      else dialog.resolve(null);
      close();
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [dialog, close]);

  if (!dialog) return null;

  const isDanger = dialog.kind === "confirm" && dialog.options.tone === "danger";

  const cancel = () => {
    if (dialog.kind === "confirm") dialog.resolve(false);
    else dialog.resolve(null);
    close();
  };

  const confirm = () => {
    if (dialog.kind === "confirm") {
      dialog.resolve(true);
      close();
      return;
    }
    const value = promptValue.trim();
    if (!value) return;
    dialog.resolve(value);
    close();
  };

  return (
    <div className="modal-backdrop app-dialog-backdrop" role="presentation" onClick={cancel}>
      <div
        className={`modal app-dialog ${isDanger ? "app-dialog--danger" : ""}`}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        onClick={(e) => e.stopPropagation()}
      >
        <h3 id={titleId}>{dialog.options.title}</h3>
        {dialog.options.description && <p className="app-dialog__desc">{dialog.options.description}</p>}

        {dialog.kind === "prompt" && (
          <label>
            {dialog.options.label}
            <input
              ref={inputRef}
              value={promptValue}
              placeholder={dialog.options.placeholder}
              onChange={(e) => setPromptValue(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") {
                  e.preventDefault();
                  confirm();
                }
              }}
            />
          </label>
        )}

        <div className="modal__actions">
          <button type="button" className="btn btn--ghost" onClick={cancel}>
            {dialog.options.cancelLabel}
          </button>
          <button
            type="button"
            className={`btn ${isDanger ? "btn--danger" : ""}`}
            disabled={dialog.kind === "prompt" && !promptValue.trim()}
            onClick={confirm}
          >
            {dialog.options.confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
