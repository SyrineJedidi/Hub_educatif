import { Link, useParams } from "react-router-dom";
import { date } from "../api/client";
import { useResource } from "../hooks/useResource";
import { Alert, Badge, Loading } from "../components/UI";
import { useQuizContext } from "./useQuizContext";
import { attemptLabels } from "./attemptTypes";
import type { ManagedResultDetail } from "./resultTypes";
import { personName, percentageLabel } from "./resultTypes";
import QuestionReview from "./QuestionReview";
import "./quiz.css";

export default function StudentResultDetail() {
  const { attemptId } = useParams();
  const { admin } = useQuizContext();
  const base = admin ? "/administration" : "/espace";
  const { data, error, loading, reload } = useResource<ManagedResultDetail>(
    `quizzes/results/${attemptId}/`,
  );
  return (
    <div className="quiz-module">
      <div className="page-heading">
        <div>
          <p className="eyebrow">CONSULTATION DES RÉPONSES</p>
          <h1>Réponses de l’étudiant</h1>
          <p>
            Retrouvez les choix enregistrés et la correction expliquée de cette
            tentative.
          </p>
        </div>
        <Link className="text-button" to={`${base}/resultats-quiz`}>
          {admin ? "Tous les résultats" : "Les résultats de mes quiz"} ↗
        </Link>
      </div>
      {loading ? (
        <Loading />
      ) : error || !data ? (
        <section className="panel">
          <Alert error={error} />
          <button className="text-button" onClick={reload}>
            Réessayer le chargement
          </button>
        </section>
      ) : (
        <>
          <section className="panel quiz-result-summary">
            <h2>{personName(data.student)}</h2>
            <p>
              {data.quiz_title} · Tentative {data.number}
            </p>
            <Badge>{attemptLabels[data.status]}</Badge>
            <dl className="quiz-facts">
              <div>
                <dt>Nom</dt>
                <dd>{data.student.last_name}</dd>
              </div>
              <div>
                <dt>Prénom</dt>
                <dd>{data.student.first_name}</dd>
              </div>
              <div>
                <dt>Groupe</dt>
                <dd>{data.learning_group.name}</dd>
              </div>
              <div>
                <dt>Enseignant</dt>
                <dd>{personName(data.teacher)}</dd>
              </div>
              <div>
                <dt>Début</dt>
                <dd>{date(data.started_at)}</dd>
              </div>
              {data.ended_at && (
                <div>
                  <dt>Fin</dt>
                  <dd>{date(data.ended_at)}</dd>
                </div>
              )}
            </dl>
            {data.status === "IN_PROGRESS" ? (
              <p className="notice">
                En cours — aucune note définitive. Les réponses ci-dessous
                peuvent encore évoluer. La correction de référence est affichée
                pour consultation.
              </p>
            ) : (
              <>
                <p className="quiz-result-score">
                  {data.points_earned} / {data.total_points} points
                </p>
                <p>
                  {data.percentage === null
                    ? "Résultat indisponible"
                    : percentageLabel(data.percentage)}
                </p>
              </>
            )}
            <Link
              className="text-button"
              to={`${base}/quiz/${data.quiz_id}/resultats`}
            >
              Résultats de ce quiz ↗
            </Link>
          </section>
          {data.questions.map((question) => (
            <article className="panel quiz-question" key={question.id}>
              <p className="notice">
                {question.selected_choice
                  ? `Réponse enregistrée de l’étudiant : ${question.selected_choice}${data.status !== "IN_PROGRESS" ? (question.is_correct ? " · Correcte" : " · Incorrecte") : ""}`
                  : "Aucune réponse enregistrée pour cette question."}
                {data.status === "IN_PROGRESS"
                  ? ` · Barème : ${question.points} point(s)`
                  : ` · ${question.points_earned} / ${question.points} point(s)`}
              </p>
              <QuestionReview
                question={{ ...question, quiz_id: data.quiz_id }}
              />
            </article>
          ))}
        </>
      )}
    </div>
  );
}
