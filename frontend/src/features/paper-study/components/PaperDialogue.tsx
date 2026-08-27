import Markdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { PaperStudy } from "../../../entities/paper-study/types";

type Props = {
  messages: PaperStudy["messages"];
  streamingUser?: string;
  streamingAssistant?: string;
  question: string;
  setQuestion: (value: string) => void;
  onSend: () => Promise<void>;
  busy: boolean;
  placeholder: string;
  sendLabel?: string;
  emptyText?: string;
  sendDisabled?: boolean;
  secondaryAction?: { label: string; onClick: () => void };
  assistantAction?: { label: string; onClick: (message: PaperStudy["messages"][number]) => void };
};

export function PaperDialogue({
  messages,
  streamingUser,
  streamingAssistant,
  question,
  setQuestion,
  onSend,
  busy,
  placeholder,
  sendLabel = "继续对话",
  emptyText,
  sendDisabled = false,
  secondaryAction,
  assistantAction,
}: Props) {
  return (
    <section className="paper-dialogue">
      <div className="paper-dialogue__messages">
        {!messages.length && !streamingUser && !streamingAssistant && emptyText && (
          <div className="paper-dialogue__empty">{emptyText}</div>
        )}
        {messages.map((message) => (
          <DialogueMessage
            key={message.id}
            role={message.role}
            content={message.content}
            action={message.role === "ASSISTANT" && assistantAction ? { label: assistantAction.label, onClick: () => assistantAction.onClick(message) } : undefined}
          />
        ))}
        {streamingUser && <DialogueMessage key="streaming-user" role="USER" content={streamingUser} />}
        {streamingAssistant && <DialogueMessage key="streaming-assistant" role="ASSISTANT" content={streamingAssistant} />}
      </div>
      <div className="paper-dialogue__composer">
        <textarea value={question} onChange={(e) => setQuestion(e.target.value)} placeholder={placeholder} />
        <button className="btn" disabled={busy || sendDisabled || !question.trim()} onClick={() => void onSend()}>
          {sendLabel}
        </button>
        {secondaryAction && (
          <button className="btn btn--ghost" type="button" onClick={secondaryAction.onClick}>
            {secondaryAction.label}
          </button>
        )}
      </div>
    </section>
  );
}

function DialogueMessage({
  role,
  content,
  action,
}: {
  role: "USER" | "ASSISTANT";
  content: string;
  action?: { label: string; onClick: () => void };
}) {
  return (
    <article className={role === "USER" ? "paper-dialogue__message user" : "paper-dialogue__message assistant"}>
      <strong>{role === "USER" ? "你" : "AI 论文阅读搭档"}</strong>
      <div className="markdown-body paper-dialogue__markdown">
        <Markdown remarkPlugins={[remarkGfm]}>{content || " "}</Markdown>
      </div>
      {action && (
        <button className="btn btn--ghost paper-dialogue__message-action" type="button" onClick={action.onClick}>
          {action.label}
        </button>
      )}
    </article>
  );
}
