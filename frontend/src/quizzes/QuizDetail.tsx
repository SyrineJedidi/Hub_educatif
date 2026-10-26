import { t, n, LanguageNotice } from "./i18n";
import { useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../api/client";
import { useResource } from "../hooks/useResource";
import { Alert, Loading, Empty, Modal, Form } from "../components/UI";
import type { Quiz, Question } from "./types";
import { useQuizContext } from "./useQuizContext";
import QuizSummary from "./QuizSummary";
import QuizActions from "./QuizActions";
import QuestionReview from "./QuestionReview";
import { QuizAttemptAccess } from "./StudentAttempts";
import "./quiz.css";
export default function QuizDetail() {
  const { id } = useParams(),
    { apiBase, base, student } = useQuizContext();
  const {
    data: quiz,
    error,
    loading,
    reload,
  } = useResource<Quiz>(apiBase + id + "/");
  if (loading) return <Loading />;
  if (!quiz) return <Alert error={error} />;
  return (
    <div className="quiz-module">
      <LanguageNotice />
      <div className="page-heading">
        <div>
          <p className="eyebrow">
            {student ? t("DÉCOUVRIR LE QUIZ") : t("VOTRE ATELIER DE QUESTIONS")}
          </p>
          <h1>{quiz.title}</h1>
          <p>{quiz.learning_group_name}</p>
        </div>
        <Link className="text-button" to={base}>
          {t("Tous les quiz ↗ ")}
        </Link>
      </div>
      <section className="panel quiz-introduction">
        <QuizSummary quiz={quiz} />
        {quiz.description && (
          <p className="quiz-description">{quiz.description}</p>
        )}
        {student ? (
          <QuizAttemptAccess quizId={quiz.id} />
        ) : (
          <>
            <div className="actions">
              <Link
                className="btn_one"
                to={base + "/" + quiz.id + "/previsualisation"}
              >
                {t("Prévisualiser ↗ ")}
              </Link>
              {quiz.status === "DRAFT" && (
                <Link
                  className="text-button"
                  to={base + "/" + quiz.id + "/generer"}
                >
                  {t("Générer des questions avec l’IA ")}
                </Link>
              )}
              {quiz.status === "DRAFT" && (
                <Link
                  className="text-button"
                  to={base + "/" + quiz.id + "/questions/nouvelle"}
                >
                  {t("Ajouter une question + ")}
                </Link>
              )}
            </div>
            <QuizActions quiz={quiz} onDone={reload} />
            {quiz.status !== "DRAFT" && (
              <p className="notice">
                {t(
                  "Ce quiz est verrouillé. Ses questions sont conservées et ne peuvent plus être modifiées. Vous pouvez le dupliquer en brouillon. ",
                )}
              </p>
            )}
          </>
        )}
      </section>
      {!student && <QuestionManager quiz={quiz} onUpdate={reload} />}
    </div>
  );
}
function QuestionManager({
  quiz,
  onUpdate,
}: {
  quiz: Quiz;
  onUpdate: () => void;
}) {
  const { base } = useQuizContext();
  const { data, error, loading, reload } = useResource<{ results: Question[] }>(
    "quizzes/" + quiz.id + "/questions/",
  );
  const [selected, setSelected] = useState<Question | null>(null),
    [actionError, setActionError] = useState<unknown>(),
    [busy, setBusy] = useState(false);
  const locked = useRef(false);
  const questions = data?.results || [];
  const editable = quiz.status === "DRAFT";
  async function move(index: number, offset: number) {
    if (locked.current) return;
    locked.current = true;
    setBusy(true);
    setActionError(undefined);
    const ids = questions.map((q) => q.id);
    [ids[index], ids[index + offset]] = [ids[index + offset], ids[index]];
    try {
      await api("quizzes/" + quiz.id + "/reorder/", "POST", {
        question_ids: ids,
      });
      reload();
      onUpdate();
    } catch (e) {
      setActionError(e);
    } finally {
      setBusy(false);
      locked.current = false;
    }
  }
  return (
    <section className="quiz-question-section">
      <div className="panel-heading">
        <h2>
          {editable ? t("Questions du brouillon") : t("Questions du quiz")}
        </h2>
        <button
          className="text-button"
          onClick={() => {
            reload();
            onUpdate();
          }}
        >
          {t("Actualiser les questions ")}
        </button>
      </div>
      <Alert error={error || actionError} />
      {loading ? (
        <Loading />
      ) : questions.length ? (
        questions.map((q, index) => (
          <article className="panel quiz-question" key={q.id}>
            <QuestionReview question={q} />
            {editable && (
              <div className="quiz-question-toolbar">
                <Link
                  to={base + "/" + quiz.id + "/questions/" + q.id + "/modifier"}
                  className="text-button"
                >
                  {t("Modifier la question ")}
                  {n(q.position)}
                </Link>
                <button className="text-button" onClick={() => setSelected(q)}>
                  {t("Supprimer la question ")}
                  {n(q.position)}
                </button>
                <div className="actions">
                  <button
                    className="quiz-order-button"
                    disabled={busy || index === 0}
                    onClick={() => void move(index, -1)}
                    aria-label={t("Monter la question ") + n(q.position)}
                  >
                    {t("↑ Monter ")}
                  </button>
                  <button
                    className="quiz-order-button"
                    disabled={busy || index === questions.length - 1}
                    onClick={() => void move(index, 1)}
                    aria-label={t("Descendre la question ") + n(q.position)}
                  >
                    {t("↓ Descendre ")}
                  </button>
                </div>
              </div>
            )}
          </article>
        ))
      ) : (
        <section className="panel">
          <Empty>
            {t(
              "Ajoutez votre première question. Un quiz doit contenir au moins une question pour être publié. ",
            )}
          </Empty>
          {editable && (
            <div className="quiz-empty-action">
              <Link
                className="btn_one"
                to={base + "/" + quiz.id + "/questions/nouvelle"}
              >
                {t("Ajouter ma première question + ")}
              </Link>
            </div>
          )}
        </section>
      )}
      {selected && (
        <Modal
          title={t("Supprimer la question ") + n(selected.position) + " ?"}
          onClose={() => setSelected(null)}
        >
          <p className="intro">
            {t(
              "La question sera supprimée de ce brouillon. Les autres questions seront conservées. ",
            )}
          </p>
          <Form
            label={t("Confirmer la suppression")}
            onSubmit={() =>
              api(
                "quizzes/" + quiz.id + "/questions/" + selected.id + "/",
                "DELETE",
              )
            }
            onSuccess={() => {
              setSelected(null);
              reload();
              onUpdate();
            }}
          />
        </Modal>
      )}
    </section>
  );
}
