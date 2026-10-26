import { Link, useLocation, useParams } from "react-router-dom";
import { useResource } from "../hooks/useResource";
import { Alert, Loading } from "../components/UI";
import type { AttemptResult as Result } from "./attemptTypes";
import QuestionReview from "./QuestionReview";
import "./quiz.css";

export default function AttemptResult() {
  const { attemptId } = useParams();
  const location = useLocation();
  const { data, error, loading } = useResource<Result>(
    `student/attempts/${attemptId}/result/`,
  );
  return (
    <div className="quiz-module">
      <div className="page-heading">
        <div>
          <p className="eyebrow">COMPRENDRE ET PROGRESSER</p>
          <h1>Votre résultat et votre correction</h1>
        </div>
        <Link className="text-button" to="/espace/tentatives">
          Mes tentatives ↗
        </Link>
      </div>
      {loading ? (
        <Loading />
      ) : !data ? (
        <>
          <Alert error={error} />
          <Link to={`/espace/tentatives/${attemptId}`}>
            Revenir à ma tentative
          </Link>
        </>
      ) : (
        <>
          <section className="panel quiz-result-summary">
            <h2>{data.quiz_title}</h2>
            <p>
              Tentative {data.number} ·{" "}
              {data.status === "EXPIRED" ? "Temps écoulé" : "Soumise"}
            </p>
            <p className="quiz-result-score">
              {data.points_earned} / {data.total_points} points
            </p>
            <p>
              {new Intl.NumberFormat("fr-FR", {
                maximumFractionDigits: 2,
              }).format(data.percentage)}{" "}
              % de réussite
            </p>
            {data.status === "EXPIRED" ? (
              <p className="notice">
                Le temps est écoulé. Seules les réponses enregistrées avant
                l’échéance ont été corrigées. Les questions sans réponse
                enregistrée valent zéro point.
              </p>
            ) : (
              location.state?.finalizedOnServer && (
                <p className="notice">
                  Cette tentative a été finalisée par le serveur. La correction
                  porte uniquement sur les réponses enregistrées.
                </p>
              )
            )}
          </section>
          {data.questions.map((question) => (
            <article className="panel quiz-question" key={question.id}>
              <p className="notice">
                {question.selected_choice
                  ? `Votre réponse : ${question.selected_choice} · ${question.is_correct ? "Correcte" : "Incorrecte"}`
                  : "Vous n’avez pas répondu à cette question."}{" "}
                · {question.points_earned} / {question.points} point(s)
              </p>
              <QuestionReview
                question={{ ...question, quiz_id: data.quiz_id }}
              />
            </article>
          ))}
          <Link className="btn_one" to="/espace/quiz">
            Retour aux quiz de mes groupes
          </Link>
        </>
      )}
    </div>
  );
}
