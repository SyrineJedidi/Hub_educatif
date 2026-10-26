import { useId } from "react";
import { date } from "../api/client";
import { Alert } from "../components/UI";
import AnswerText from "./AnswerText";
import SourceList from "./SourceList";
import FeedbackControls, { FeedbackOutcome } from "./FeedbackControls";
import type { Feedback, InputMode, Message } from "./types";
import { messageStatuses } from "./types";
import { duration, time } from "./format";
export function StatusBadge({
  kind,
  children,
}: {
  kind: "warning" | "error" | "info";
  children: string;
}) {
  return (
    <span className={"status-badge assistant-badge-" + kind}>{children}</span>
  );
}
export interface Pending {
  key: string;
  clientId: string;
  content: string;
  inputMode: InputMode;
  state: "sending" | "error";
  error?: unknown;
}
export function PendingQuestion({
  item,
  canResend,
  onResend,
  onEdit,
}: {
  item: Pending;
  canResend: boolean;
  onResend: () => void;
  onEdit: () => void;
}) {
  const heading = useId();
  return (
    <article
      className="assistant-message is-user is-pending"
      aria-labelledby={heading}
      aria-busy={item.state === "sending" ? true : undefined}
    >
      <h3 id={heading} className="visually-hidden">
        Vous ·{" "}
        {item.state === "sending"
          ? "question en cours d’envoi"
          : "question non envoyée"}
      </h3>
      <p className="assistant-pre">{item.content}</p>
      {item.state === "sending" ? (
        <p className="assistant-meta">Envoi…</p>
      ) : (
        <>
          <Alert error={item.error} />
          <div className="actions">
            <button
              className="text-button"
              aria-disabled={canResend ? undefined : true}
              onClick={() => {
                if (canResend) onResend();
              }}
            >
              Renvoyer la question
            </button>
            <button className="text-button" onClick={onEdit}>
              Modifier la question
            </button>
          </div>
        </>
      )}
    </article>
  );
}
export function UserMessage({ message }: { message: Message }) {
  const heading = useId();
  return (
    <article className="assistant-message is-user" aria-labelledby={heading}>
      <h3 id={heading} className="visually-hidden">
        Vous · {date(message.created_at)}
      </h3>
      <p className="assistant-pre">{message.content}</p>
      <p className="assistant-meta">
        {message.input_mode === "VOICE" && (
          <>
            <span className="ti-microphone" aria-hidden="true" /> Question
            dictée ·{" "}
          </>
        )}
        <time dateTime={message.created_at}>{time(message.created_at)}</time>
      </p>
    </article>
  );
}
export default function MessageItem({
  message,
  ordinal,
  question,
  showFollowUps,
  canRetry,
  canFeedback,
  teacher,
  onRetry,
  onFollowUp,
  onFeedback,
  announce,
}: {
  message: Message;
  ordinal: number;
  question?: Message;
  showFollowUps: boolean;
  canRetry: boolean;
  canFeedback: boolean;
  teacher: boolean;
  onRetry: (question: Message) => void;
  onFollowUp: (text: string) => void;
  onFeedback: (id: string, feedback: Feedback | null) => void;
  announce: (text: string) => void;
}) {
  const heading = useId();
  if (message.role === "USER") return <UserMessage message={message} />;
  const label = message.status_label || messageStatuses[message.status];
  const answered =
    message.status === "COMPLETE" || message.status === "OUT_OF_SCOPE";
  return (
    <article
      className={
        "assistant-message is-assistant is-" + message.status.toLowerCase()
      }
      aria-labelledby={heading}
    >
      <h3 id={heading} className="visually-hidden">
        Assistant, réponse {ordinal} · {date(message.created_at)}
      </h3>
      {(message.status !== "COMPLETE" || message.unsourced) && (
        <p className="assistant-badges">
          {message.status === "OUT_OF_SCOPE" && (
            <StatusBadge kind="info">{label}</StatusBadge>
          )}
          {(message.status === "FAILED" || message.status === "BLOCKED") && (
            <StatusBadge kind="error">{label}</StatusBadge>
          )}
          {message.status === "COMPLETE" && message.unsourced && (
            <StatusBadge kind="warning">Réponse non sourcée</StatusBadge>
          )}
        </p>
      )}
      {answered ? (
        <AnswerText
          text={message.content}
          anchor={"source-" + message.id}
          citations={message.citations}
        />
      ) : (
        <p className="assistant-pre">{message.content}</p>
      )}
      {message.status === "COMPLETE" && message.unsourced && (
        <p className="assistant-hint">
          Aucun extrait du cours ne confirme cette réponse : vérifiez-la dans
          vos supports ou auprès de votre enseignant.
        </p>
      )}
      {message.status === "OUT_OF_SCOPE" && (
        <p className="assistant-hint">
          Le contenu du cours ne permet pas de répondre. Reformulez la question
          avec les termes du cours ou posez-la à votre enseignant.
        </p>
      )}
      {message.status === "BLOCKED" && (
        <p className="assistant-hint">
          Reformulez votre question en restant sur le contenu du cours.
        </p>
      )}
      <SourceList
        citations={message.citations}
        anchor={"source-" + message.id}
      />
      {message.status === "FAILED" && canRetry && question && (
        <button
          type="button"
          className="text-button assistant-retry"
          onClick={() => onRetry(question)}
        >
          <span className="ti-reload" aria-hidden="true" /> Réessayer
          <span className="visually-hidden"> (réponse {ordinal})</span>
        </button>
      )}
      {showFollowUps && message.follow_ups.length > 0 && (
        <div className="assistant-followups">
          <p>Pour aller plus loin :</p>
          <ul>
            {message.follow_ups.map((text) => (
              <li key={text}>
                <button type="button" onClick={() => onFollowUp(text)}>
                  {text}
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}
      <p className="assistant-meta">
        <time dateTime={message.created_at}>{time(message.created_at)}</time>
        {message.status === "COMPLETE" &&
          !!message.latency_ms &&
          " · Réponse en " + duration(message.latency_ms)}
      </p>
      {answered && canFeedback ? (
        <FeedbackControls
          message={message}
          ordinal={ordinal}
          teacher={teacher}
          onChange={(feedback) => onFeedback(message.id, feedback)}
          announce={announce}
        />
      ) : (
        message.feedback && <FeedbackOutcome feedback={message.feedback} />
      )}
    </article>
  );
}
