import { ApiError } from "./client";

export type SseHandler = (event: string, data: unknown) => void;

async function parseError(response: Response): Promise<ApiError> {
  try {
    const body = await response.json();
    const code = body?.error?.code ?? "UNKNOWN_ERROR";
    const message = body?.error?.message ?? response.statusText;
    return new ApiError(response.status, code, message);
  } catch {
    return new ApiError(response.status, "UNKNOWN_ERROR", response.statusText);
  }
}

/** Consume a text/event-stream response and invoke handler per SSE event. */
export async function consumeSse(
  response: Response,
  onEvent: SseHandler,
  signal?: AbortSignal,
): Promise<void> {
  if (!response.ok) {
    throw await parseError(response);
  }
  if (!response.body) {
    throw new ApiError(500, "SSE_NO_BODY", "响应没有可读流");
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder("utf-8");
  let buffer = "";

  try {
    while (true) {
      if (signal?.aborted) {
        await reader.cancel();
        break;
      }
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const chunks = buffer.split("\n\n");
      buffer = chunks.pop() ?? "";
      for (const chunk of chunks) {
        const lines = chunk.split("\n");
        let event = "message";
        const dataLines: string[] = [];
        for (const line of lines) {
          if (line.startsWith("event:")) event = line.slice(6).trim();
          else if (line.startsWith("data:")) dataLines.push(line.slice(5).trim());
        }
        if (!dataLines.length) continue;
        const raw = dataLines.join("\n");
        let data: unknown = raw;
        try {
          data = JSON.parse(raw);
        } catch {
          /* keep string */
        }
        onEvent(event, data);
      }
    }
  } finally {
    reader.releaseLock();
  }
}
