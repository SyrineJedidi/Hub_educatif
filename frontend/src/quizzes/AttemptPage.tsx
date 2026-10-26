import { t, n, LanguageNotice } from "./i18n";
import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api, ApiError } from "../api/client";
import { useResource } from "../hooks/useResource";
import { Alert, Form, Loading, Modal } from "../components/UI";
import type { Attempt, Choice } from "./attemptTypes";
import { useAnswerQueue } from "./useAnswerQueue";
import UnsavedChanges from "./UnsavedChanges";
import "./quiz.css";

export default function AttemptPage() {
  const { attemptId } = useParams();
  const { data, error, loading, reload } = useResource<Attempt>(
    `student/attempts/${attemptId}/`,
  );
  return loading ? (
    <Loading />
  ) : !data ? (
    <div>
      <Alert error={error} />
      <button className="text-button" onClick={reload}>
        {t("Réessayer le chargement ")}
      </button>
    </div>
  ) : (
    <AttemptRunner key={data.id} initial={data} />
  );
}

function AttemptRunner({ initial }: { initial: Attempt }) {
  const navigate = useNavigate();
  const completed = useRef(false),
    mounted = useRef(true),
    refreshing = useRef(false);
  const anchor = useRef({
    server: Date.parse(initial.server_time),
    local: performance.now(),
  });
  const [now, setNow] = useState(anchor.current.server);
  const [error, setError] = useState<unknown>();
  const [denied, setDenied] = useState(false),
    [confirm, setConfirm] = useState(false),
    [submitting, setSubmitting] = useState(false),
    [conflict, setConflict] = useState(false);
  const refresh = useCallback(async () => {
    if (refreshing.current) return;
    refreshing.current = true;
    try {
      const latest = await api<Attempt>(`student/attempts/${initial.id}/`);
      if (!mounted.current) return;
      anchor.current = {
        server: Date.parse(latest.server_time),
        local: performance.now(),
      };
      setNow(anchor.current.server);
      setError(undefined);
      if (latest.status !== "IN_PROGRESS") {
        completed.current = true;
        navigate(`/espace/tentatives/${initial.id}/resultat`, {
          replace: true,
          state: { finalizedOnServer: true },
        });
      }
    } catch (error) {
      if (mounted.current) {
        setError(error);
        if (error instanceof ApiError && [401, 403, 404].includes(error.status))
          setDenied(true);
      }
    } finally {
      refreshing.current = false;
    }
  }, [initial.id, navigate]);
  const queue = useAnswerQueue(initial, refresh);
  useEffect(() => {
    mounted.current = true;
    if (initial.status !== "IN_PROGRESS") {
      completed.current = true;
      navigate(`/espace/tentatives/${initial.id}/resultat`, { replace: true });
    }
    let expiryChecked = false;
    const tick = setInterval(() => {
      const serverNow =
        anchor.current.server + performance.now() - anchor.current.local;
      setNow(serverNow);
      if (
        initial.deadline &&
        serverNow >= Date.parse(initial.deadline) &&
        !expiryChecked
      ) {
        expiryChecked = true;
        void refresh();
      }
    }, 1000);
    const poll = setInterval(() => void refresh(), 15000);
    const visible = () => {
      if (document.visibilityState === "visible") void refresh();
    };
    document.addEventListener("visibilitychange", visible);
    return () => {
      mounted.current = false;
      clearInterval(tick);
      clearInterval(poll);
      document.removeEventListener("visibilitychange", visible);
    };
  }, [initial.id, initial.deadline, initial.status, navigate, refresh]);
  const remaining = initial.deadline
    ? Math.max(0, Math.ceil((Date.parse(initial.deadline) - now) / 1000))
    : null;
  const answered = Object.keys(queue.answers).length;
  const blocked =
    initial.status !== "IN_PROGRESS" ||
    denied ||
    submitting ||
    remaining === 0 ||
    queue.conflict ||
    conflict;
  async function submit() {
    setError(undefined);
    queue.freeze(true);
    setSubmitting(true);
    try {
      const versions = await queue.flush();
      await api(`student/attempts/${initial.id}/submit/`, "POST", {
        answer_revisions: versions,
      });
      completed.current = true;
      if (mounted.current)
        navigate(`/espace/tentatives/${initial.id}/resultat`, {
          replace: true,
        });
    } catch (error) {
      if (mounted.current) setError(error);
      if (
        error instanceof ApiError &&
        error.code === "answers_not_synchronized"
      )
        setConflict(true);
      throw error;
    } finally {
      queue.freeze(false);
      setSubmitting(false);
    }
  }
  return (
    <div className="quiz-module">
      <LanguageNotice />
      <UnsavedChanges dirty={queue.dirty || submitting} ignore={completed} />
      <div className="page-heading">
        <div>
          <p className="eyebrow">
            {t("TENTATIVE ")}
            {n(initial.number)}
            {t(" · À VOTRE RYTHME")}
          </p>
          <h1>{initial.quiz_title}</h1>
          <p>
            {t(
              "Choisissez une réponse par question. Chaque sélection est enregistrée dès confirmation du serveur. ",
            )}
          </p>
        </div>
        <Link className="text-button" to="/espace/tentatives">
          {t("Mes tentatives ↗ ")}
        </Link>
      </div>
      <Alert error={error} />
      {(queue.conflict || conflict) && (
        <div className="notice notice-error" role="alert">
          <p>
            {t(
              "Les réponses ont changé dans une autre fenêtre. Vérifiez les réponses du serveur avant de continuer. ",
            )}
          </p>
          <button
            className="text-button"
            onClick={() => window.location.reload()}
          >
            {t("Recharger les réponses du serveur ")}
          </button>
        </div>
      )}
      <section
        className="panel quiz-attempt-progress"
        aria-label={t("Progression de la tentative")}
      >
        <div>
          <strong>
            {n(answered)} / {n(initial.questions.length)}
            {t(" questions répondues ")}
          </strong>
          <progress
            aria-label={t("Questions répondues")}
            value={answered}
            max={initial.questions.length}
          />
        </div>
        {remaining !== null ? (
          <p
            className="quiz-timer"
            role="timer"
            aria-label={t("Temps restant")}
          >
            {t("Temps restant :")}{" "}
            <strong>
              {n(Math.floor(remaining / 60))}:
              {n(remaining % 60).padStart(2, n(0))}
            </strong>
          </p>
        ) : (
          <p>{t("Durée illimitée")}</p>
        )}
        <p role="status">
          {queue.dirty
            ? t(
                "Des réponses restent à synchroniser. Elles ne sont pas encore toutes enregistrées.",
              )
            : answered
              ? t("Toutes vos réponses sélectionnées sont enregistrées.")
              : t("Aucune réponse sélectionnée.")}
        </p>
        {remaining === 0 && (
          <p className="notice">
            {t(
              "Le temps est écoulé. Vérification de la tentative auprès du serveur… Seules les réponses enregistrées avant l’échéance seront corrigées. ",
            )}
          </p>
        )}
        {!!error && (
          <button className="text-button" onClick={() => void refresh()}>
            {t("Vérifier l’état de la tentative ")}
          </button>
        )}
      </section>
      {initial.questions.map((question, index) => {
        const answer = queue.answers[question.id];
        return (
          <section className="panel quiz-question" key={question.id}>
            <fieldset className="quiz-answer-fieldset" disabled={blocked}>
              <legend>
                {t("Question ")}
                {n(index + 1)} · {n(question.points)}
                {t(" point(s) ")}
              </legend>
              <p className="quiz-statement">{question.statement}</p>
              <div className="quiz-answer-grid">
                {(["A", "B", "C", "D"] as Choice[]).map((letter) => (
                  <label
                    className={`quiz-answer quiz-taking-choice ${answer?.choice === letter ? "is-selected" : ""}`}
                    key={letter}
                  >
                    <input
                      type="radio"
                      name={question.id}
                      value={letter}
                      checked={answer?.choice === letter}
                      onChange={() => queue.select(question.id, letter)}
                    />
                    <span className="quiz-letter" aria-hidden="true">
                      {letter}
                    </span>
                    <span>
                      {question[`choice_${letter.toLowerCase()}` as "choice_a"]}
                    </span>
                  </label>
                ))}
              </div>
            </fieldset>
            <div className="quiz-save-status" role="status" aria-live="polite">
              {answer?.state === "saved" ? (
                t("Enregistré")
              ) : answer?.state === "saving" || answer?.state === "pending" ? (
                t("Enregistrement…")
              ) : answer?.state === "error" ? (
                <>
                  <span className="notice-error">
                    {answer.error}
                    {t(" Votre sélection n’est pas confirmée. ")}
                  </span>
                  {!queue.conflict && !blocked && (
                    <button
                      className="text-button"
                      onClick={() => void queue.retry()}
                    >
                      {t("Réessayer l’enregistrement ")}
                    </button>
                  )}
                </>
              ) : (
                t("Pas encore de réponse.")
              )}
            </div>
          </section>
        );
      })}
      <section className="panel">
        <h2>{t("Terminer votre tentative")}</h2>
        <p>
          {t(
            "Vérifiez vos choix avant de soumettre. Les questions sans réponse valent zéro point. ",
          )}
        </p>
        <button
          className="btn_one"
          disabled={blocked}
          onClick={() => setConfirm(true)}
        >
          {t("Terminer ma tentative ")}
        </button>
      </section>
      {confirm && (
        <Modal
          title={t("Soumettre votre tentative ?")}
          onClose={() => setConfirm(false)}
        >
          <p>
            {t("Il reste ")}
            {n(initial.questions.length - answered)}
            {t(" question(s) sans réponse. ")}
          </p>
          <p>
            {queue.dirty
              ? t(
                  "Les réponses en attente doivent être enregistrées avant la soumission. En cas d’erreur, la tentative restera ouverte.",
                )
              : t(
                  "Toutes vos sélections sont enregistrées. Après soumission, elles ne seront plus modifiables.",
                )}
          </p>
          {queue.conflict || conflict ? (
            <button
              className="text-button"
              onClick={() => window.location.reload()}
            >
              {t("Recharger les réponses du serveur ")}
            </button>
          ) : (
            <Form label={t("Enregistrer et soumettre")} onSubmit={submit} />
          )}
        </Modal>
      )}
    </div>
  );
}
