import { t, n, LanguageNotice } from "./i18n";
import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api, date } from "../api/client";
import { useResource } from "../hooks/useResource";
import type { Page } from "../api/types";
import { Alert, Empty, Form, Loading, Pagination } from "../components/UI";
import type { Attempt, AttemptSummary, QuizAttempts } from "./attemptTypes";
import { attemptLabels, attemptPath } from "./attemptTypes";
import "./quiz.css";
import { ProgressSummary } from "./Progress";

export function AttemptLinks({ attempts }: { attempts: AttemptSummary[] }) {
  return (
    <div className="quiz-attempt-history">
      {attempts.map((attempt) => (
        <article className="quiz-attempt-row" key={attempt.id}>
          <div>
            <h3>
              {attempt.quiz_title}
              {t(" · Tentative ")}
              {n(attempt.number)}
            </h3>
            <p>
              {t(attemptLabels[attempt.status])}
              {attempt.points_earned !== null
                ? ` · ${n(attempt.points_earned)} / ${n(attempt.total_points)} ${t("points")}`
                : ""}
            </p>
          </div>
          <Link className="text-button" to={attemptPath(attempt)}>
            {attempt.status === "IN_PROGRESS"
              ? t("Reprendre")
              : t("Voir ma correction")}{" "}
            ↗
          </Link>
        </article>
      ))}
    </div>
  );
}

export function QuizAttemptAccess({ quizId }: { quizId: string }) {
  const { data, error, loading, reload } = useResource<QuizAttempts>(
    `student/quizzes/${quizId}/attempts/`,
  );
  const navigate = useNavigate();
  const [elapsed, setElapsed] = useState(0);
  useEffect(() => {
    setElapsed(0);
    if (!data?.availability.can_start || !data.availability.closes_at) return;
    const started = performance.now();
    const timer = setInterval(
      () => setElapsed((performance.now() - started) / 1000),
      1000,
    );
    return () => clearInterval(timer);
  }, [data]);
  const window = data?.availability;
  const availableSeconds =
    window?.available_seconds == null
      ? null
      : window.closes_at
        ? Math.max(
            0,
            Math.min(
              window.available_seconds,
              Math.floor(
                (Date.parse(window.closes_at) -
                  Date.parse(window.server_time)) /
                  1000 -
                  elapsed,
              ),
            ),
          )
        : window.available_seconds;
  useEffect(() => {
    if (!data?.availability) return;
    const target =
      data.availability.state === "UPCOMING"
        ? data.availability.opens_at
        : data.availability.state === "OPEN"
          ? data.availability.closes_at
          : null;
    if (!target) return;
    const delay =
      Date.parse(target) - Date.parse(data.availability.server_time);
    const timer = setTimeout(
      reload,
      Math.max(100, Math.min(delay + 50, 60000)),
    );
    return () => clearTimeout(timer);
  }, [data]);
  return (
    <section className="quiz-attempt-access" aria-label={t("Passage du quiz")}>
      <h2>{t("À vous de jouer")}</h2>
      {loading ? (
        <Loading />
      ) : !data ? (
        <div>
          <Alert error={error} />
          <button className="text-button" onClick={reload}>
            {t("Réessayer le chargement des tentatives ")}
          </button>
        </div>
      ) : (
        <>
          <p>
            {n(data.attempts_used)}
            {t(" tentative(s) utilisée(s) sur")} {n(data.max_attempts)}
            {t(". Chaque tentative soumise ou expirée est comptabilisée. ")}
          </p>
          {data.current_attempt_id ? (
            <Link
              className="btn_one"
              to={`/espace/tentatives/${data.current_attempt_id}`}
            >
              {t("Reprendre ")}
            </Link>
          ) : data.remaining_attempts > 0 &&
            data.quiz_status === "PUBLISHED" &&
            data.availability.can_start ? (
            <>
              <p className="notice">
                {t(
                  "L’échéance est la plus proche entre la durée et la fermeture du quiz. Temps disponible au départ : ",
                )}
                {availableSeconds === null
                  ? t("Sans limite de temps")
                  : t("{0} min {1} s", [
                      Math.floor(availableSeconds / 60),
                      availableSeconds % 60,
                    ])}
                {t(". L’heure serveur fait référence.")}
              </p>
              <Form
                label={t("Commencer le quiz")}
                onSubmit={async () => {
                  const attempt = await api<Attempt>(
                    `student/quizzes/${quizId}/attempts/`,
                    "POST",
                    {},
                  );
                  navigate(attemptPath(attempt));
                }}
              />
            </>
          ) : (
            <p className="notice">
              {data.availability.state === "UPCOMING"
                ? t("À venir — ouverture : {0} (Africa/Tunis).", [
                    date(data.availability.opens_at!),
                  ])
                : data.availability.state === "CLOSED"
                  ? t("Ce quiz est fermé. Aucun nouveau départ n’est possible.")
                  : data.quiz_status !== "PUBLISHED"
                    ? t("Ce quiz ne permet plus de nouveau départ.")
                    : t(
                        "Limite de tentatives atteinte. Vous avez utilisé toutes vos tentatives autorisées.",
                      )}
            </p>
          )}
          {data.attempts.length > 0 && (
            <>
              <h3>{t("Mes tentatives pour ce quiz")}</h3>
              <AttemptLinks attempts={data.attempts} />
            </>
          )}
        </>
      )}
      <Link className="text-button" to="/espace/tentatives">
        {t("Toutes mes tentatives et corrections ↗ ")}
      </Link>
    </section>
  );
}

export default function StudentAttempts() {
  const [page, setPage] = useState(1);
  const { data, error, loading } = useResource<Page<AttemptSummary>>(
    `student/attempts/?page=${page}`,
  );
  return (
    <div className="quiz-module">
      <LanguageNotice />
      <div className="page-heading">
        <div>
          <p className="eyebrow">{t("VOTRE PARCOURS")}</p>
          <h1>{t("Mes résultats")}</h1>
          <p>
            {t(
              "Reprenez vos réponses enregistrées et retrouvez vos corrections, y compris pour un quiz archivé si vous avez toujours accès à son groupe. ",
            )}
          </p>
        </div>
        <Link className="text-button" to="/espace/quiz">
          {t("Les quiz de mes groupes ↗ ")}
        </Link>
      </div>
      <ProgressSummary />
      {loading ? (
        <Loading />
      ) : !data ? (
        <Alert error={error} />
      ) : (
        <section className="panel">
          {data.count ? (
            <AttemptLinks attempts={data.results} />
          ) : (
            <Empty>
              {t(
                "Vous n’avez pas encore commencé de quiz. Choisissez un quiz publié dans vos groupes pour commencer. ",
              )}
            </Empty>
          )}
          <Pagination page={page} count={data.count} onChange={setPage} />
        </section>
      )}
    </div>
  );
}
