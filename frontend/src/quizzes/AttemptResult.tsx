import { t, n, LanguageNotice, locale } from "./i18n";
import { Link, useLocation, useParams } from "react-router-dom";
import { useResource } from "../hooks/useResource";
import { Alert, Loading } from "../components/UI";
import type { AttemptResult as Result } from "./attemptTypes";
import QuestionReview from "./QuestionReview";
import { StudentFeedback } from "./Feedback";
import "./quiz.css";

export default function AttemptResult() {
  const { attemptId } = useParams();
  const location = useLocation();
  const { data, error, loading } = useResource<Result>(
    `student/attempts/${attemptId}/result/`,
  );
  return (
    <div className="quiz-module">
      <LanguageNotice />
      <div className="page-heading">
        <div>
          <p className="eyebrow">{t("COMPRENDRE ET PROGRESSER")}</p>
          <h1>{t("Votre résultat et votre correction")}</h1>
        </div>
        <Link className="text-button" to="/espace/tentatives">
          {t("Mes tentatives ↗ ")}
        </Link>
      </div>
      {loading ? (
        <Loading />
      ) : !data ? (
        <>
          <Alert error={error} />
          <Link to={`/espace/tentatives/${attemptId}`}>
            {t("Revenir à ma tentative ")}
          </Link>
        </>
      ) : (
        <>
          <section className="panel quiz-result-summary">
            <h2>{data.quiz_title}</h2>
            <p>
              {t("Tentative ")}
              {n(data.number)} ·{" "}
              {data.status === "EXPIRED" ? t("Temps écoulé") : t("Soumise")}
            </p>
            <p className="quiz-result-score">
              {n(data.points_earned)} / {n(data.total_points)}
              {t(" points ")}
            </p>
            <p>
              {new Intl.NumberFormat(locale(), {
                maximumFractionDigits: 2,
              }).format(data.percentage)}{" "}
              {t("% de réussite ")}
            </p>
            {data.status === "EXPIRED" ? (
              <p className="notice">
                {t(
                  "Le temps est écoulé. Seules les réponses enregistrées avant l’échéance ont été corrigées. Les questions sans réponse enregistrée valent zéro point. ",
                )}
              </p>
            ) : (
              location.state?.finalizedOnServer && (
                <p className="notice">
                  {t(
                    "Cette tentative a été finalisée par le serveur. La correction porte uniquement sur les réponses enregistrées. ",
                  )}
                </p>
              )
            )}
          </section>
          {data.questions.map((question) => (
            <article className="panel quiz-question" key={question.id}>
              <p
                className={`notice quiz-answer-outcome ${!question.selected_choice ? "is-unanswered" : question.is_correct ? "is-correct" : "is-incorrect"}`}
              >
                {question.selected_choice
                  ? t("Votre réponse : {0} · {1}", [
                      question.selected_choice,
                      question.is_correct ? t("Correcte") : t("Incorrecte"),
                    ])
                  : t("Vous n’avez pas répondu à cette question.")}{" "}
                · {n(question.points_earned)} / {n(question.points)}
                {t(" point(s) ")}
              </p>
              <QuestionReview
                question={{ ...question, quiz_id: data.quiz_id }}
              />
            </article>
          ))}
          <StudentFeedback quizId={data.quiz_id} />
          <Link className="btn_one" to="/espace/quiz">
            {t("Retour aux quiz de mes groupes ")}
          </Link>
        </>
      )}
    </div>
  );
}
