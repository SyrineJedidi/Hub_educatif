import { t, n, LanguageNotice } from "./i18n";
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
      <LanguageNotice />
      <div className="page-heading">
        <div>
          <p className="eyebrow">{t("CONSULTATION DES RÉPONSES")}</p>
          <h1>{t("Réponses de l’étudiant")}</h1>
          <p>
            {t(
              "Retrouvez les choix enregistrés et la correction expliquée de cette tentative. ",
            )}
          </p>
        </div>
        <Link className="text-button" to={`${base}/resultats-quiz`}>
          {admin ? t("Tous les résultats") : t("Les résultats de mes quiz")} ↗
        </Link>
      </div>
      {loading ? (
        <Loading />
      ) : error || !data ? (
        <section className="panel">
          <Alert error={error} />
          <button className="text-button" onClick={reload}>
            {t("Réessayer le chargement ")}
          </button>
        </section>
      ) : (
        <>
          <section className="panel quiz-result-summary">
            <h2>{personName(data.student)}</h2>
            <p>
              {data.quiz_title}
              {t(" · Tentative ")}
              {n(data.number)}
            </p>
            <Badge>{t(attemptLabels[data.status])}</Badge>
            <dl className="quiz-facts">
              <div>
                <dt>{t("Nom")}</dt>
                <dd>{data.student.last_name}</dd>
              </div>
              <div>
                <dt>{t("Prénom")}</dt>
                <dd>{data.student.first_name}</dd>
              </div>
              <div>
                <dt>{t("Groupe")}</dt>
                <dd>{data.learning_group.name}</dd>
              </div>
              <div>
                <dt>{t("Enseignant")}</dt>
                <dd>{personName(data.teacher)}</dd>
              </div>
              <div>
                <dt>{t("Début")}</dt>
                <dd>{date(data.started_at)}</dd>
              </div>
              {data.ended_at && (
                <div>
                  <dt>{t("Fin")}</dt>
                  <dd>{date(data.ended_at)}</dd>
                </div>
              )}
            </dl>
            {data.status === "IN_PROGRESS" ? (
              <p className="notice">
                {t(
                  "En cours — aucune note définitive. Les réponses ci-dessous peuvent encore évoluer. La correction de référence est affichée pour consultation. ",
                )}
              </p>
            ) : (
              <>
                <p className="quiz-result-score">
                  {n(data.points_earned)} / {n(data.total_points)}
                  {t(" points ")}
                </p>
                <p>
                  {data.percentage === null
                    ? t("Résultat indisponible")
                    : percentageLabel(data.percentage)}
                </p>
              </>
            )}
            <Link
              className="text-button"
              to={`${base}/quiz/${data.quiz_id}/resultats`}
            >
              {t("Résultats de ce quiz ↗ ")}
            </Link>
          </section>
          {data.questions.map((question) => (
            <article className="panel quiz-question" key={question.id}>
              <p
                className={`notice quiz-answer-outcome ${!question.selected_choice ? "is-unanswered" : data.status === "IN_PROGRESS" ? "" : question.is_correct ? "is-correct" : "is-incorrect"}`}
              >
                {question.selected_choice
                  ? t("Réponse enregistrée de l’étudiant : {0}{1}", [
                      question.selected_choice,
                      data.status !== "IN_PROGRESS"
                        ? question.is_correct
                          ? t(" · Correcte")
                          : t(" · Incorrecte")
                        : "",
                    ])
                  : t("Aucune réponse enregistrée pour cette question.")}
                {data.status === "IN_PROGRESS"
                  ? t(" · Barème : {0} point(s)", [question.points])
                  : ` · ${n(question.points_earned)} / ${n(question.points)} ${t("point(s)")}`}
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
