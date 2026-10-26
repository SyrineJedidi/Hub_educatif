import { t, n, LanguageNotice } from "./i18n";
import { useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api } from "../api/client";
import { useResource } from "../hooks/useResource";
import { Field, Textarea, Form, Alert, Loading } from "../components/UI";
import type { Quiz, Question } from "./types";
import { useQuizContext } from "./useQuizContext";
import UnsavedChanges from "./UnsavedChanges";
import { validateQuestion } from "./validation";
import { useFormValidation } from "./useFormValidation";
import "./quiz.css";
export default function QuestionEditor() {
  const { id, questionId } = useParams();
  const {
    data: quiz,
    error,
    loading,
  } = useResource<Quiz>("quizzes/" + id + "/");
  return (
    <div className="quiz-module">
      <LanguageNotice />
      <div className="page-heading">
        <div>
          <p className="eyebrow">{t("QCM À RÉPONSE UNIQUE")}</p>
          <h1>
            {questionId ? t("Modifier la question") : t("Ajouter une question")}
          </h1>
          <p>{t("Quatre propositions distinctes, une seule bonne réponse.")}</p>
        </div>
      </div>
      {loading ? (
        <Loading />
      ) : !quiz ? (
        <Alert error={error} />
      ) : quiz.status !== "DRAFT" ? (
        <Alert error="Ce quiz est verrouillé. Ses questions ne sont plus modifiables." />
      ) : questionId ? (
        <ExistingQuestion quiz={quiz} questionId={questionId} />
      ) : (
        <QuestionForm quiz={quiz} />
      )}
    </div>
  );
}
function ExistingQuestion({
  quiz,
  questionId,
}: {
  quiz: Quiz;
  questionId: string;
}) {
  const { data, error, loading } = useResource<Question>(
    "quizzes/" + quiz.id + "/questions/" + questionId + "/",
  );
  return loading ? (
    <Loading />
  ) : data ? (
    <QuestionForm key={data.id} quiz={quiz} question={data} />
  ) : (
    <Alert error={error} />
  );
}
function QuestionForm({ quiz, question }: { quiz: Quiz; question?: Question }) {
  const { base } = useQuizContext(),
    navigate = useNavigate(),
    saved = useRef(false);
  const [values, setValues] = useState({
    statement: question?.statement || "",
    choice_a: question?.choice_a || "",
    choice_b: question?.choice_b || "",
    choice_c: question?.choice_c || "",
    choice_d: question?.choice_d || "",
    correct_answer: question?.correct_answer || "",
    explanation: question?.explanation || "",
    points: String(question?.points || 1),
    position: String(question?.position || quiz.next_position || 1),
  });
  const [dirty, setDirty] = useState(false);
  const validation = useFormValidation(() => validateQuestion(values), values);
  const { errors } = validation;
  function update(field: keyof typeof values, value: string) {
    setValues((v) => ({ ...v, [field]: value }));
    setDirty(true);
  }
  async function submit() {
    validation.check();
    try {
      await api(
        "quizzes/" +
          quiz.id +
          "/questions/" +
          (question ? question.id + "/" : ""),
        question ? "PATCH" : "POST",
        {
          ...values,
          statement: values.statement.trim(),
          explanation: values.explanation.trim(),
          points: Number(values.points),
          position: Number(values.position),
        },
      );
      saved.current = true;
      setDirty(false);
      navigate(base + "/" + quiz.id, { replace: true });
    } catch (e) {
      validation.serverErrors(e);
      throw e;
    }
  }
  return (
    <>
      <UnsavedChanges dirty={dirty} ignore={saved} />
      <section className="panel quiz-context">
        <p className="eyebrow">{t("VOTRE BROUILLON")}</p>
        <h2>{quiz.title}</h2>
        <p>
          {quiz.learning_group_name} · {n(quiz.question_count)}
          {t(" questions ·")} {n(quiz.total_points)}
          {t(" points ")}
        </p>
      </section>
      <Form
        {...validation.formProps}
        onSubmit={submit}
        label={
          question ? t("Enregistrer la question") : t("Ajouter au brouillon")
        }
      >
        <p className="field-help">
          {t(
            "Tous les champs affichés sont obligatoires, y compris l’explication dès l’enregistrement du brouillon. La position suivante est proposée automatiquement. ",
          )}
        </p>
        <section className="panel">
          <h2>{t("L’énoncé")}</h2>
          <Textarea
            label={t("Énoncé de la question")}
            name="statement"
            rows={4}
            required
            maxLength={2000}
            value={values.statement}
            onChange={(e) => update("statement", e.target.value)}
            error={errors.statement}
          />
        </section>
        <section className="panel">
          <fieldset className="quiz-answer-fieldset">
            <legend>{t("Les quatre propositions")}</legend>
            <p className="field-help">
              {t(
                "Chaque proposition doit être différente. Cochez exactement une bonne réponse. ",
              )}
            </p>
            <div className="quiz-answer-grid">
              {(["a", "b", "c", "d"] as const).map((letter) => {
                const field = ("choice_" + letter) as
                  | "choice_a"
                  | "choice_b"
                  | "choice_c"
                  | "choice_d";
                return (
                  <div
                    className={
                      "quiz-answer " +
                      (values.correct_answer === letter.toUpperCase()
                        ? "is-correct"
                        : "")
                    }
                    key={letter}
                  >
                    <span className="quiz-letter" aria-hidden="true">
                      {letter.toUpperCase()}
                    </span>
                    <Textarea
                      label={t("Proposition ") + letter.toUpperCase()}
                      name={field}
                      required
                      maxLength={500}
                      rows={3}
                      value={values[field]}
                      onChange={(e) => update(field, e.target.value)}
                      error={errors[field]}
                    />
                    <label className="quiz-answer-radio">
                      <input
                        type="radio"
                        name="correct_answer"
                        value={letter.toUpperCase()}
                        checked={values.correct_answer === letter.toUpperCase()}
                        required
                        aria-invalid={errors.correct_answer ? true : undefined}
                        onChange={(e) =>
                          update("correct_answer", e.target.value)
                        }
                        aria-describedby={
                          errors.correct_answer
                            ? "correct-answer-error"
                            : undefined
                        }
                      />{" "}
                      {letter.toUpperCase()}
                      {t(" est la bonne réponse ")}
                    </label>
                  </div>
                );
              })}
            </div>
            {errors.correct_answer && (
              <p
                id="correct-answer-error"
                className="notice notice-error"
                role="alert"
              >
                {errors.correct_answer}
              </p>
            )}
          </fieldset>
        </section>
        <section className="panel">
          <h2>{t("La correction et les points")}</h2>
          <Textarea
            label={t("Explication de correction")}
            name="explanation"
            required
            rows={4}
            value={values.explanation}
            onChange={(e) => update("explanation", e.target.value)}
            error={errors.explanation}
          />
          <p className="field-help">
            {t(
              "Expliquez la correction dès l’enregistrement du brouillon. Les extraits de code, accents, apostrophes et symboles sont autorisés. ",
            )}
          </p>
          <div className="form-grid">
            <Field
              label={t("Points de la question")}
              name="points"
              type="number"
              min={1}
              max={10}
              step={1}
              required
              value={values.points}
              onChange={(e) => update("points", e.target.value)}
              error={errors.points}
            />
            <Field
              label={t("Position dans le quiz")}
              name="position"
              type="number"
              min={1}
              max={2147483647}
              step={1}
              required
              value={values.position}
              onChange={(e) => update("position", e.target.value)}
              error={errors.position}
            />
          </div>
          <p className="field-help">
            {t(
              "La position suivante est proposée automatiquement. Vous pourrez déplacer les questions depuis la liste. ",
            )}
          </p>
        </section>
        <div className="quiz-form-cancel">
          <Link to={base + "/" + quiz.id}>{t("Annuler")}</Link>
        </div>
      </Form>
    </>
  );
}
