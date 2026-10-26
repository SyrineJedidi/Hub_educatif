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
      <div className="page-heading">
        <div>
          <p className="eyebrow">ESPACE DE CONCEPTION · CORRECTION VISIBLE</p>
          <h1>Prévisualisation enseignant</h1>
          <p>
            Vérifiez les questions et leurs explications avant de partager le
            quiz.
          </p>
        </div>
        <Link className="text-button" to={base + "/" + quiz.id}>
          Revenir au quiz ↗
        </Link>
      </div>
      <section className="panel quiz-introduction">
        <h2>{quiz.title}</h2>
        <p className="quiz-description">{quiz.description}</p>
        <QuizSummary quiz={quiz} />
        <p className="field-help">
          Ceci est une prévisualisation de gestion. Elle ne constitue pas un
          passage de quiz et ne calcule aucun résultat étudiant.
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
              ? "À compléter avant publication"
              : "Votre quiz est prêt à être publié"}
          </h2>
          {blockers.length ? (
            <>
              <p>Les éléments suivants empêchent la publication :</p>
              <ul>
                {blockers.map((reason, i) => (
                  <li key={i}>{reason}</li>
                ))}
              </ul>
              <Link className="text-button" to={base + "/" + quiz.id}>
                Revenir aux questions pour corriger ↗
              </Link>
            </>
          ) : (
            <>
              <p className="intro">
                Toutes les questions possèdent quatre propositions distinctes,
                une bonne réponse et une explication.
              </p>
              <button className="btn_one" onClick={() => setConfirm(true)}>
                Publier le quiz
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
          <Empty>Ce quiz ne contient pas encore de question.</Empty>
        </section>
      )}
      {confirm && (
        <Modal title="Publier ce quiz ?" onClose={() => setConfirm(false)}>
          <p className="intro">
            Les étudiants autorisés du groupe « {quiz.learning_group_name} »
            verront sa présentation. Le quiz et ses {questions.length} questions
            seront verrouillés. Pour les retravailler ensuite, il faudra
            dupliquer le quiz.
          </p>
          <Form
            label="Confirmer la publication"
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
