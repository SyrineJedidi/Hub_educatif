import { useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { ApiError, date } from "../api/client";
import { useResource } from "../hooks/useResource";
import { Alert, Form, Loading, Modal, Textarea, val } from "../components/UI";
import { actOnReview, reviewPath } from "./api";
import AnswerText from "./AnswerText";
import SourceList from "./SourceList";
import { AssistantManagerNav, AssistantUnavailable } from "./AssistantRoutes";
import type { Review, ReviewAction } from "./types";
import { feedbackStatuses, ratings } from "./types";
import { reasonLabels } from "./format";
import { useAssistantContext } from "./useAssistantContext";
import "./assistant.css";
const CORRECTION_MAX = 2000;
// The answer, without its citation markers, is a starting point when it fits.
function correctionDraft(answer: string) {
  const text = answer.replace(/\s*\[S\d+(?:\s*[,;]\s*S?\d+)*\]/g, "").trim();
  return text.length <= CORRECTION_MAX ? text : "";
}
const copy: Record<
  ReviewAction,
  {
    button: string;
    title: string;
    intro: string;
    confirm: string;
    done: string;
  }
> = {
  CONFIRM: {
    button: "Confirmer la réponse",
    title: "Confirmer cette réponse ?",
    intro:
      "L’étudiant verra « Réponse confirmée par votre enseignant » sous la réponse. Vous pouvez ajouter une note.",
    confirm: "Confirmer la réponse",
    done: "Réponse confirmée.",
  },
  CORRECT: {
    button: "Publier une correction",
    title: "Publier une correction",
    intro:
      "La correction s’affiche sous la réponse de l’étudiant. Elle est aussi ajoutée aux sources de ce cours : l’assistant la citera en priorité pour les questions proches.",
    confirm: "Publier la correction",
    done: "Correction publiée : l’assistant l’utilisera désormais.",
  },
  DISMISS: {
    button: "Classer sans suite",
    title: "Classer ce signalement sans suite ?",
    intro:
      "Le signalement sort de la file. Vous pouvez expliquer votre décision à l’étudiant.",
    confirm: "Classer sans suite",
    done: "Signalement classé sans suite.",
  },
};
export default function ReviewDetail() {
  const { id = "" } = useParams(),
    { base } = useAssistantContext();
  const { data, error, loading, reload } = useResource<Review>(reviewPath(id));
  const [updated, setUpdated] = useState<Review | null>(null),
    [action, setAction] = useState<ReviewAction | null>(null),
    [done, setDone] = useState("");
  const outcome = useRef<HTMLHeadingElement>(null);
  if (loading && !data) return <Loading />;
  if (!data)
    return (
      <AssistantUnavailable
        title="Signalement indisponible"
        error={error}
        onRetry={reload}
      />
    );
  const review = updated?.id === data.id ? updated : data;
  const open = review.status === "NEW";
  return (
    <div className="assistant-module">
      <div className="page-heading">
        <div>
          <p className="eyebrow">SIGNALEMENT · {review.scope_title}</p>
          <h1>Examiner une réponse</h1>
          <p>
            Signalé le {date(review.created_at)}. L’identité de l’étudiant n’est
            jamais communiquée.
          </p>
        </div>
        <Link className="text-button" to={base + "/signalements"}>
          Tous les signalements ↗
        </Link>
      </div>
      <AssistantManagerNav />
      <section className="panel" aria-labelledby="review-question">
        <h2 id="review-question">Question de l’étudiant</h2>
        <p className="assistant-pre">{review.question}</p>
      </section>
      <section className="panel" aria-labelledby="review-answer">
        <h2 id="review-answer">Réponse de l’assistant</h2>
        <p className="assistant-meta">
          Donnée le {date(review.answer.created_at)}
        </p>
        <AnswerText
          text={review.answer.content}
          anchor={"source-" + review.id}
          citations={review.answer.citations}
        />
        <SourceList
          citations={review.answer.citations}
          anchor={"source-" + review.id}
          headingLevel={3}
        />
      </section>
      <section className="panel" aria-labelledby="review-feedback">
        <h2 id="review-feedback">Retour de l’étudiant</h2>
        <dl className="assistant-facts">
          <div>
            <dt>Avis</dt>
            <dd>{ratings[review.rating]}</dd>
          </div>
          <div>
            <dt>Motifs</dt>
            <dd>{reasonLabels(review).join(", ") || "Aucun motif"}</dd>
          </div>
          <div>
            <dt>Commentaire</dt>
            <dd className="assistant-pre">
              {review.comment || "Aucun commentaire"}
            </dd>
          </div>
        </dl>
      </section>
      <section className="panel" aria-labelledby="review-outcome">
        <h2 id="review-outcome" ref={outcome} tabIndex={-1}>
          Décision
        </h2>
        <Alert success={done} />
        <p>
          Statut :{" "}
          <span className="status-badge">
            {review.status_label || feedbackStatuses[review.status]}
          </span>
          {review.reviewed_at && <> · le {date(review.reviewed_at)}</>}
        </p>
        {review.teacher_note && (
          <div className="assistant-outcome">
            <p>
              <strong>
                {review.status === "CORRECTED"
                  ? "Correction publiée"
                  : "Note pour l’étudiant"}
              </strong>
            </p>
            <p className="assistant-pre">{review.teacher_note}</p>
          </div>
        )}
        {open ? (
          <div className="actions">
            {(Object.keys(copy) as ReviewAction[]).map((item) => (
              <button
                key={item}
                className={item === "CORRECT" ? "btn_one" : "text-button"}
                onClick={() => {
                  setDone("");
                  setAction(item);
                }}
              >
                {copy[item].button}
              </button>
            ))}
          </div>
        ) : (
          <p className="field-help">
            Ce signalement a déjà été traité : sa décision ne peut plus être
            modifiée.
          </p>
        )}
      </section>
      {action && (
        <Modal title={copy[action].title} onClose={() => setAction(null)}>
          <p className="intro">{copy[action].intro}</p>
          <Form
            label={copy[action].confirm}
            onSubmit={async (form) => {
              try {
                const result = await actOnReview(review.id, {
                  action,
                  ...(action === "CORRECT"
                    ? { correction: val(form, "correction").trim() }
                    : { note: val(form, "note").trim() }),
                });
                if (result) setUpdated(result);
              } catch (e) {
                if (e instanceof ApiError && e.code === "already_reviewed")
                  reload();
                throw e;
              }
            }}
            onSuccess={() => {
              const message = copy[action].done;
              setAction(null);
              setDone(message);
              requestAnimationFrame(() => outcome.current?.focus());
            }}
          >
            {action === "CORRECT" ? (
              <Textarea
                label="Réponse corrigée"
                name="correction"
                required
                rows={10}
                maxLength={CORRECTION_MAX}
                defaultValue={correctionDraft(review.answer.content)}
              />
            ) : (
              <Textarea
                label="Note pour l’étudiant (facultatif)"
                name="note"
                rows={4}
                maxLength={2000}
              />
            )}
          </Form>
        </Modal>
      )}
    </div>
  );
}
