import { useEffect, useId, useRef, useState } from "react";
import type { FormEvent } from "react";
import { Alert } from "../components/UI";
import { deleteFeedback, saveFeedback } from "./api";
import type { Feedback, Message, Reason } from "./types";
import { FEEDBACK_COMMENT_MAX, reasons } from "./types";
export function FeedbackOutcome({ feedback }: { feedback: Feedback }) {
  if (feedback.status === "CONFIRMED")
    return (
      <div className="assistant-outcome is-confirmed">
        <p>
          <span className="ti-check" aria-hidden="true" /> Réponse confirmée par
          votre enseignant.
        </p>
        {feedback.teacher_note && <p>{feedback.teacher_note}</p>}
      </div>
    );
  if (feedback.status === "CORRECTED")
    return (
      <div className="assistant-outcome is-corrected">
        <p>
          <strong>Correction de votre enseignant</strong>
        </p>
        <p className="assistant-pre">{feedback.teacher_note}</p>
      </div>
    );
  if (feedback.status === "DISMISSED")
    return (
      <div className="assistant-outcome">
        <p>Votre enseignant a examiné ce retour et l’a classé sans suite.</p>
        {feedback.teacher_note && <p>{feedback.teacher_note}</p>}
      </div>
    );
  return feedback.shared_with_teacher ? (
    <p className="assistant-outcome-pending">
      Retour transmis à votre enseignant, sans votre nom.
    </p>
  ) : null;
}
export default function FeedbackControls({
  message,
  ordinal,
  teacher,
  onChange,
  announce,
}: {
  message: Message;
  ordinal: number;
  teacher: boolean;
  onChange: (feedback: Feedback | null) => void;
  announce: (text: string) => void;
}) {
  const current = message.feedback || null;
  const [open, setOpen] = useState(false),
    [busy, setBusy] = useState(false),
    [error, setError] = useState<unknown>(),
    [reasonError, setReasonError] = useState("");
  const [selected, setSelected] = useState<Reason[]>([]),
    [comment, setComment] = useState(""),
    [shared, setShared] = useState(false);
  const downButton = useRef<HTMLButtonElement>(null),
    fieldset = useRef<HTMLFieldSetElement>(null);
  const id = useId();
  const locked = !!current && current.status !== "NEW";
  const suffix = " (réponse " + ordinal + ")";
  useEffect(() => {
    if (open)
      fieldset.current?.querySelector<HTMLInputElement>("input")?.focus();
  }, [open]);
  async function persist(next: Feedback | null, run: () => Promise<unknown>) {
    const previous = current;
    setBusy(true);
    setError(undefined);
    onChange(next);
    try {
      const saved = await run();
      if (next && saved && typeof saved === "object" && "rating" in saved)
        onChange(saved as Feedback);
      return true;
    } catch (e) {
      onChange(previous);
      setError(e);
      return false;
    } finally {
      setBusy(false);
    }
  }
  async function useful() {
    if (busy || locked) return;
    setOpen(false);
    if (current?.rating === "UP") {
      if (await persist(null, () => deleteFeedback(message.id)))
        announce("Votre avis a été retiré.");
      return;
    }
    const body = {
      rating: "UP" as const,
      reasons: [],
      comment: "",
      shared_with_teacher: false,
    };
    if (
      await persist(
        { ...body, status: "NEW", status_label: "Nouveau", teacher_note: "" },
        () => saveFeedback(message.id, body),
      )
    )
      announce("Merci pour votre retour.");
  }
  function improve() {
    if (busy || locked) return;
    if (open) {
      setOpen(false);
      return;
    }
    setSelected(current?.rating === "DOWN" ? current.reasons : []);
    setComment(current?.rating === "DOWN" ? current.comment : "");
    setShared(current?.rating === "DOWN" ? current.shared_with_teacher : false);
    setReasonError("");
    setError(undefined);
    setOpen(true);
  }
  function close() {
    setOpen(false);
    downButton.current?.focus();
  }
  async function submit(e: FormEvent) {
    e.preventDefault();
    if (busy) return;
    if (!selected.length) {
      setReasonError("Choisissez au moins un motif.");
      fieldset.current?.querySelector<HTMLInputElement>("input")?.focus();
      return;
    }
    const body = {
      rating: "DOWN" as const,
      reasons: selected,
      comment: comment.trim(),
      shared_with_teacher: shared,
    };
    if (
      await persist(
        { ...body, status: "NEW", status_label: "Nouveau", teacher_note: "" },
        () => saveFeedback(message.id, body),
      )
    ) {
      close();
      announce(
        shared
          ? "Merci pour votre retour : il a été transmis à votre enseignant."
          : "Merci pour votre retour.",
      );
    }
  }
  async function remove() {
    if (busy) return;
    if (await persist(null, () => deleteFeedback(message.id))) {
      close();
      announce("Votre avis a été retiré.");
    }
  }
  return (
    <div className="assistant-feedback">
      <div className="assistant-feedback-buttons">
        <span className="assistant-feedback-label">
          Cette réponse vous aide-t-elle ?
        </span>
        <button
          type="button"
          className="assistant-toggle"
          aria-pressed={current?.rating === "UP"}
          aria-disabled={busy || locked ? true : undefined}
          onClick={() => void useful()}
        >
          <span className="ti-thumb-up" aria-hidden="true" /> Utile
          <span className="visually-hidden">{suffix}</span>
        </button>
        <button
          ref={downButton}
          type="button"
          className="assistant-toggle"
          aria-pressed={current?.rating === "DOWN"}
          aria-disabled={busy || locked ? true : undefined}
          onClick={improve}
        >
          <span className="ti-thumb-down" aria-hidden="true" /> À améliorer
          <span className="visually-hidden">{suffix}</span>
        </button>
      </div>
      {!open && <Alert error={error} />}
      {open && (
        <form className="assistant-feedback-form" onSubmit={submit} noValidate>
          <fieldset
            ref={fieldset}
            aria-describedby={reasonError ? id + "-reasons" : undefined}
          >
            <legend>
              Qu’est-ce qui ne va pas ?
              <span className="visually-hidden">{suffix}</span>
            </legend>
            <div className="assistant-reasons">
              {(Object.keys(reasons) as Reason[]).map((reason) => (
                <label key={reason} className="assistant-check">
                  <input
                    type="checkbox"
                    checked={selected.includes(reason)}
                    onChange={(e) => {
                      setReasonError("");
                      setSelected((items) =>
                        e.target.checked
                          ? [...items, reason]
                          : items.filter((item) => item !== reason),
                      );
                    }}
                  />
                  {reasons[reason]}
                </label>
              ))}
            </div>
            {reasonError && (
              <p id={id + "-reasons"} className="field-help notice-error">
                {reasonError}
              </p>
            )}
          </fieldset>
          <div className="field">
            <label htmlFor={id + "-comment"}>Commentaire (facultatif)</label>
            <textarea
              id={id + "-comment"}
              className="form-control"
              rows={3}
              maxLength={FEEDBACK_COMMENT_MAX}
              value={comment}
              aria-describedby={id + "-count"}
              onChange={(e) => setComment(e.target.value)}
            />
            <p id={id + "-count"} className="field-help">
              {comment.length} / {FEEDBACK_COMMENT_MAX} caractères
            </p>
          </div>
          <label className="assistant-check">
            <input
              type="checkbox"
              checked={shared}
              aria-describedby={id + "-share"}
              onChange={(e) => setShared(e.target.checked)}
            />
            {teacher
              ? "Ajouter à la file des signalements"
              : "Partager avec l’enseignant"}
          </label>
          <p id={id + "-share"} className="field-help">
            {teacher
              ? "Le retour apparaîtra dans vos signalements pour être corrigé."
              : "Votre enseignant verra la question et la réponse, sans votre nom, et pourra publier une correction. Celle-ci serait visible par les autres étudiants du cours, avec votre question telle qu’il l’aura relue."}
          </p>
          <Alert error={error} />
          <div className="actions">
            <button className="btn_one" aria-disabled={busy ? true : undefined}>
              {busy ? "Envoi…" : "Envoyer mon retour"}
            </button>
            <button type="button" className="text-button" onClick={close}>
              Annuler
            </button>
            {current?.rating === "DOWN" && current.status === "NEW" && (
              <button
                type="button"
                className="text-button"
                onClick={() => void remove()}
              >
                Retirer mon avis
              </button>
            )}
          </div>
        </form>
      )}
      {current && <FeedbackOutcome feedback={current} />}
    </div>
  );
}
