import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api } from "../api/client";
import { useResource } from "../hooks/useResource";
import type { Page } from "../api/types";
import { Alert, Empty, Form, Loading, Pagination } from "../components/UI";
import type { Attempt, AttemptSummary, QuizAttempts } from "./attemptTypes";
import { attemptLabels, attemptPath } from "./attemptTypes";
import "./quiz.css";

export function AttemptLinks({ attempts }: { attempts: AttemptSummary[] }) {
  return (
    <div className="quiz-attempt-history">
      {attempts.map((attempt) => (
        <article className="quiz-attempt-row" key={attempt.id}>
          <div>
            <h3>
              {attempt.quiz_title} · Tentative {attempt.number}
            </h3>
            <p>
              {attemptLabels[attempt.status]}
              {attempt.points_earned !== null
                ? ` · ${attempt.points_earned} / ${attempt.total_points} points`
                : ""}
            </p>
          </div>
          <Link className="text-button" to={attemptPath(attempt)}>
            {attempt.status === "IN_PROGRESS"
              ? "Reprendre"
              : "Voir ma correction"}{" "}
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
  return (
    <section className="quiz-attempt-access" aria-label="Passage du quiz">
      <h2>À vous de jouer</h2>
      {loading ? (
        <Loading />
      ) : !data ? (
        <div>
          <Alert error={error} />
          <button className="text-button" onClick={reload}>
            Réessayer le chargement des tentatives
          </button>
        </div>
      ) : (
        <>
          <p>
            {data.attempts_used} tentative(s) utilisée(s) sur{" "}
            {data.max_attempts}. Chaque tentative soumise ou expirée est
            comptabilisée.
          </p>
          {data.current_attempt_id ? (
            <Link
              className="btn_one"
              to={`/espace/tentatives/${data.current_attempt_id}`}
            >
              Reprendre
            </Link>
          ) : data.remaining_attempts > 0 &&
            data.quiz_status === "PUBLISHED" ? (
            <Form
              label="Commencer le quiz"
              onSubmit={async () => {
                const attempt = await api<Attempt>(
                  `student/quizzes/${quizId}/attempts/`,
                  "POST",
                  {},
                );
                navigate(attemptPath(attempt));
              }}
            />
          ) : (
            <p className="notice">
              {data.quiz_status !== "PUBLISHED"
                ? "Ce quiz ne permet plus de nouveau départ."
                : "Limite de tentatives atteinte. Vous avez utilisé toutes vos tentatives autorisées."}
            </p>
          )}
          {data.attempts.length > 0 && (
            <>
              <h3>Mes tentatives pour ce quiz</h3>
              <AttemptLinks attempts={data.attempts} />
            </>
          )}
        </>
      )}
      <Link className="text-button" to="/espace/tentatives">
        Toutes mes tentatives et corrections ↗
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
      <div className="page-heading">
        <div>
          <p className="eyebrow">VOTRE PARCOURS</p>
          <h1>Mes tentatives et corrections</h1>
          <p>
            Reprenez vos réponses enregistrées et retrouvez vos corrections, y
            compris pour un quiz archivé si vous avez toujours accès à son
            groupe.
          </p>
        </div>
        <Link className="text-button" to="/espace/quiz">
          Les quiz de mes groupes ↗
        </Link>
      </div>
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
              Vous n’avez pas encore commencé de quiz. Choisissez un quiz publié
              dans vos groupes pour commencer.
            </Empty>
          )}
          <Pagination page={page} count={data.count} onChange={setPage} />
        </section>
      )}
    </div>
  );
}
