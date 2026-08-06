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
  secondaryAction?: { label: string; onClick: () => void };
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
  secondaryAction,
}: Props) {
  return (
    <section className="paper-dialogue">
      <div className="paper-dialogue__messages">
        {messages.map((message) => (
          <DialogueMessage key={message.id} role={message.role} content={message.content} />
        ))}
        {streamingUser && <DialogueMessage key="streaming-user" role="USER" content={streamingUser} />}
        {streamingAssistant && <DialogueMessage key="streaming-assistant" role="ASSISTANT" content={streamingAssistant} />}
      </div>
      <div className="paper-dialogue__composer">
        <textarea value={question} onChange={(e) => setQuestion(e.target.value)} placeholder={placeholder} />
        <button className="btn" disabled={busy || !question.trim()} onClick={() => void onSend()}>
          继续对话
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

function DialogueMessage({ role, content }: { role: "USER" | "ASSISTANT"; content: string }) {
  return (
    <article className={role === "USER" ? "paper-dialogue__message user" : "paper-dialogue__message assistant"}>
      <strong>{role === "USER" ? "你" : "AI 论文阅读搭档"}</strong>
      <div className="markdown-body paper-dialogue__markdown">
        <Markdown remarkPlugins={[remarkGfm]}>{content || " "}</Markdown>
      </div>
    </article>
  );
}
