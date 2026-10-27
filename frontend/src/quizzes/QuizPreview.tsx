import { t, n, publicationReason, LanguageNotice } from "./i18n";
import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api } from "../api/client";
import { useResource } from "../hooks/useResource";
import { Alert, Loading, Empty, Modal, Form } from "../components/UI";
import type { Preview } from "./types";
import { useQuizContext } from "./useQuizContext";
import QuizSummary from "./QuizSummary";
import QuestionReview from "./QuestionReview";
import "./quiz.css";
export default function QuizPreview() {
  const { id } = useParams(),
    { base } = useQuizContext(),
    navigate = useNavigate();
  const { data, error, loading } = useResource<Preview>(
    "quizzes/" + id + "/preview/",
  );
  const [confirm, setConfirm] = useState(false);
  if (loading) return <Loading />;
  if (!data) return <Alert error={error} />;
  const { quiz, questions, publication_blockers: blockers } = data;
  return (
    <div className="quiz-module">
      <LanguageNotice />
      <div className="page-heading">
        <div>
          <p className="eyebrow">
            {t("ESPACE DE CONCEPTION · CORRECTION VISIBLE")}
          </p>
          <h1>{t("Prévisualisation enseignant")}</h1>
          <p>
            {t(
              "Vérifiez les questions et leurs explications avant de partager le quiz. ",
            )}
          </p>
        </div>
        <Link className="text-button" to={base + "/" + quiz.id}>
          {t("Revenir au quiz ↗ ")}
        </Link>
      </div>
      <section className="panel quiz-introduction">
        <h2>{quiz.title}</h2>
        <p className="quiz-description">{quiz.description}</p>
        <QuizSummary quiz={quiz} />
        <p className="field-help">
          {t(
            "Ceci est une prévisualisation de gestion. Elle ne constitue pas un passage de quiz et ne calcule aucun résultat étudiant. ",
          )}
        </p>
      </section>
      {quiz.status === "DRAFT" && (
        <section
          className={
            "panel quiz-publication " + (blockers.length ? "has-blockers" : "")
          }
        >
          <h2>
            {blockers.length
              ? t("À compléter avant publication")
              : t("Votre quiz est prêt à être publié")}
          </h2>
          {blockers.length ? (
            <>
              <p>{t("Les éléments suivants empêchent la publication :")}</p>
              <ul>
                {blockers.map((reason, i) => (
                  <li key={i}>{publicationReason(reason)}</li>
                ))}
              </ul>
              <Link className="text-button" to={base + "/" + quiz.id}>
                {t("Revenir aux questions pour corriger ↗ ")}
              </Link>
            </>
          ) : (
            <>
              <p className="intro">
                {t(
                  "Toutes les questions possèdent quatre propositions distinctes, une bonne réponse et une explication. ",
                )}
              </p>
              <button className="btn_one" onClick={() => setConfirm(true)}>
                {t("Publier le quiz ")}
              </button>
            </>
          )}
        </section>
      )}
      {questions.length ? (
        questions.map((q) => (
          <article key={q.id} className="panel quiz-question">
            <QuestionReview question={q} />
          </article>
        ))
      ) : (
        <section className="panel">
          <Empty>{t("Ce quiz ne contient pas encore de question.")}</Empty>
        </section>
      )}
      {confirm && (
        <Modal title={t("Publier ce quiz ?")} onClose={() => setConfirm(false)}>
          <p className="intro">
            {t("Les étudiants autorisés du groupe « ")}
            {quiz.learning_group_name}
            {t(" » verront sa présentation. Le quiz et ses ")}
            {n(questions.length)}
            {t(
              " questions seront verrouillés. Pour les retravailler ensuite, il faudra dupliquer le quiz. ",
            )}
          </p>
          <Form
            label={t("Confirmer la publication")}
            onSubmit={() => api("quizzes/" + quiz.id + "/publish/", "POST", {})}
            onSuccess={() => {
              setConfirm(false);
              navigate(base + "/" + quiz.id, { replace: true });
            }}
          />
        </Modal>
      )}
    </div>
  );
}
