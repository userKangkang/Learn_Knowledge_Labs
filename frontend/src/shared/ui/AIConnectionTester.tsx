import { useEffect, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { getLlmSettings, testLlmConnection, type LLMConnectionTestResult } from "../api/llm";
import { ApiError } from "../api/client";

type TestResult =
  | { kind: "success"; data: LLMConnectionTestResult }
  | { kind: "error"; code: string; message: string };
type Position = { left: number; top: number };

const POSITION_STORAGE_KEY = "knowledge-labs:ai-connection-position";

function defaultModel(settings: Awaited<ReturnType<typeof getLlmSettings>>) {
  if (settings.default_text_provider === "kimi") return settings.kimi_model;
  if (settings.default_text_provider === "openai") return settings.openai_model;
  return settings.model;
}

export function AIConnectionTester() {
  const [expanded, setExpanded] = useState(false);
  const [selectedModel, setSelectedModel] = useState("");
  const [testing, setTesting] = useState(false);
  const [result, setResult] = useState<TestResult | null>(null);
  const [position, setPosition] = useState<Position | null>(() => {
    if (typeof window === "undefined") return null;
    try {
      const stored = JSON.parse(window.localStorage.getItem(POSITION_STORAGE_KEY) ?? "null") as Partial<Position> | null;
      if (stored && Number.isFinite(stored.left) && Number.isFinite(stored.top)) {
        return { left: stored.left as number, top: stored.top as number };
      }
    } catch {
      /* localStorage may be unavailable */
    }
    return null;
  });
  const [dragging, setDragging] = useState(false);
  const testerRef = useRef<HTMLDivElement | null>(null);
  const dragRef = useRef<{ offsetX: number; offsetY: number; pointerId: number } | null>(null);
  const settingsQuery = useQuery({
    queryKey: ["llm", "settings"],
    queryFn: getLlmSettings,
    enabled: expanded,
  });
  const settings = settingsQuery.data;
  const options = settings
    ? [
        { label: "DeepSeek · " + settings.model, value: settings.model, configured: settings.api_key_configured },
        { label: "Kimi · " + settings.kimi_model, value: settings.kimi_model, configured: settings.kimi_api_key_configured },
        { label: "OpenAI · " + settings.openai_model, value: settings.openai_model, configured: settings.openai_api_key_configured },
      ]
    : [];

  useEffect(() => {
    if (settings && !selectedModel) setSelectedModel(defaultModel(settings));
  }, [settings, selectedModel]);

  useEffect(() => {
    if (position) window.localStorage.setItem(POSITION_STORAGE_KEY, JSON.stringify(position));
  }, [position]);

  const handlePointerDown = (event: React.PointerEvent<HTMLElement>) => {
    if ((event.target as HTMLElement).closest("button, select, input, textarea")) return;
    const rect = testerRef.current?.getBoundingClientRect();
    if (!rect) return;
    dragRef.current = {
      offsetX: event.clientX - rect.left,
      offsetY: event.clientY - rect.top,
      pointerId: event.pointerId,
    };
    event.currentTarget.setPointerCapture(event.pointerId);
    setDragging(true);
  };

  const handlePointerMove = (event: React.PointerEvent<HTMLElement>) => {
    const drag = dragRef.current;
    const rect = testerRef.current?.getBoundingClientRect();
    if (!drag || !rect || drag.pointerId !== event.pointerId) return;
    const left = Math.min(
      Math.max(0, event.clientX - drag.offsetX),
      Math.max(0, window.innerWidth - rect.width),
    );
    const top = Math.min(
      Math.max(0, event.clientY - drag.offsetY),
      Math.max(0, window.innerHeight - rect.height),
    );
    setPosition({ left, top });
  };

  const handlePointerUp = (event: React.PointerEvent<HTMLElement>) => {
    if (dragRef.current?.pointerId !== event.pointerId) return;
    dragRef.current = null;
    if (event.currentTarget.hasPointerCapture(event.pointerId)) {
      event.currentTarget.releasePointerCapture(event.pointerId);
    }
    setDragging(false);
  };
  const dragHandlers = {
    onPointerDown: handlePointerDown,
    onPointerMove: handlePointerMove,
    onPointerUp: handlePointerUp,
    onPointerCancel: handlePointerUp,
  };
  const positionStyle = position ? { left: position.left, top: position.top, right: "auto" } : undefined;

  const test = async () => {
    if (!selectedModel || testing) return;
    setTesting(true);
    setResult(null);
    try {
      setResult({ kind: "success", data: await testLlmConnection(selectedModel) });
    } catch (error) {
      if (error instanceof ApiError) {
        setResult({ kind: "error", code: error.code, message: error.message });
      } else {
        setResult({ kind: "error", code: "CLIENT_ERROR", message: error instanceof Error ? error.message : "AI 连接测试失败" });
      }
    } finally {
      setTesting(false);
    }
  };

  return (
    <div
      ref={testerRef}
      className={
        "ai-connection-tester" +
        (expanded ? " is-expanded" : "") +
        (dragging ? " is-dragging" : "")
      }
      style={positionStyle}
    >
      {!expanded ? (
        <div className="ai-connection-tester__toggle" {...dragHandlers}>
          <span className="ai-connection-tester__grip" title="拖动窗口">⠿</span>
          <button type="button" className="ai-connection-tester__toggle-button" aria-expanded={false} onClick={() => setExpanded(true)}>
            <span
              className={
                result?.kind === "success"
                  ? "ai-connection-tester__dot is-ok"
                  : result?.kind === "error"
                    ? "ai-connection-tester__dot is-error"
                    : "ai-connection-tester__dot"
              }
            />
            AI 连接
          </button>
        </div>
      ) : (
        <section className="ai-connection-tester__panel" aria-label="AI 连接测试">
          <header {...dragHandlers}>
            <div>
              <span className="ai-connection-tester__grip" title="拖动窗口">⠿</span>
              <span className="eyebrow">AI CONNECTIVITY</span>
              <strong>AI 连接测试</strong>
            </div>
            <button type="button" className="ai-connection-tester__collapse" onClick={() => setExpanded(false)}>
              收起
            </button>
          </header>
          <p className="ai-connection-tester__hint">发送一条固定测试指令；有回复即表示当前模型连接正常。</p>
          {settingsQuery.isLoading && <p className="muted">读取模型配置…</p>}
          {settingsQuery.error && <p className="error-text">{(settingsQuery.error as Error).message}</p>}
          {settings && (
            <>
              <label className="ai-connection-tester__field">
                测试模型
                <select value={selectedModel} onChange={(event) => setSelectedModel(event.target.value)} disabled={testing}>
                  {options.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}{option.configured ? "" : "（未配置 Key）"}
                    </option>
                  ))}
                </select>
              </label>
              <button type="button" className="btn ai-connection-tester__test" onClick={() => void test()} disabled={testing || !selectedModel}>
                {testing ? "测试中…" : "测试连接"}
              </button>
            </>
          )}
          {result?.kind === "success" && (
            <div className="ai-connection-tester__result is-success">
              <strong>连接正常</strong>
              <span>{result.data.provider} / {result.data.model} · {result.data.latency_ms} ms</span>
              <pre>{result.data.response}</pre>
            </div>
          )}
          {result?.kind === "error" && (
            <div className="ai-connection-tester__result is-error">
              <strong>连接失败 · {result.code}</strong>
              <pre>{result.message}</pre>
            </div>
          )}
        </section>
      )}
    </div>
  );
}
