import { useId } from "react";
import type { KeyboardEvent, ReactNode, Ref } from "react";
import { QUESTION_MAX } from "./types";
import { count } from "./format";
export default function Composer({
  value,
  onChange,
  onSubmit,
  busy,
  locked,
  lockMessage,
  error,
  textareaRef,
  voice,
}: {
  value: string;
  onChange: (value: string) => void;
  onSubmit: () => void;
  busy: boolean;
  locked: boolean;
  lockMessage?: string;
  error?: string;
  textareaRef: Ref<HTMLTextAreaElement>;
  voice?: ReactNode;
}) {
  const id = useId();
  const describedBy = [
    lockMessage ? id + "-lock" : "",
    id + "-help",
    id + "-count",
    error ? id + "-error" : "",
  ]
    .filter(Boolean)
    .join(" ");
  function keyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    // keyCode 229 covers browsers that do not set isComposing during IME input.
    if (
      e.key === "Enter" &&
      !e.shiftKey &&
      !e.nativeEvent.isComposing &&
      e.keyCode !== 229
    ) {
      e.preventDefault();
      onSubmit();
    }
  }
  return (
    <form
      className="assistant-composer"
      aria-label="Poser une question"
      onSubmit={(e) => {
        e.preventDefault();
        onSubmit();
      }}
    >
      {lockMessage && (
        <p id={id + "-lock"} className="notice assistant-lock">
          {lockMessage}
        </p>
      )}
      <label htmlFor={id}>Votre question</label>
      <textarea
        id={id}
        ref={textareaRef}
        className="form-control"
        rows={3}
        maxLength={QUESTION_MAX}
        value={value}
        readOnly={locked}
        aria-invalid={error ? true : undefined}
        aria-describedby={describedBy}
        placeholder="Par exemple : peux-tu m’expliquer la notion vue au chapitre 2 ?"
        onChange={(e) => onChange(e.target.value)}
        onKeyDown={keyDown}
      />
      <div className="assistant-composer-meta">
        <p id={id + "-help"}>
          Entrée pour envoyer, Maj+Entrée pour aller à la ligne.
        </p>
        <p id={id + "-count"}>
          {count(value.length)} / {count(QUESTION_MAX)} caractères
        </p>
      </div>
      {error && (
        <p id={id + "-error"} className="field-help notice-error">
          {error}
        </p>
      )}
      <div className="assistant-composer-actions">
        {voice}
        <button
          className="btn_one"
          aria-disabled={busy || locked ? true : undefined}
        >
          {busy ? "Envoi…" : "Envoyer"}
          <span className="visually-hidden"> la question</span>
        </button>
      </div>
    </form>
  );
}
