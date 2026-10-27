import { t, LanguageNotice } from "./i18n";
import { useEffect, useRef, useState } from "react";
import type { FormEvent } from "react";
import { Link, useParams } from "react-router-dom";
import { api, ApiError } from "../api/client";
import { Alert, Field, Loading, Select, Textarea } from "../components/UI";
import { useResource } from "../hooks/useResource";
import type { Quiz } from "./types";
import { levels } from "./types";
import { validateQuestion } from "./validation";
import type { FieldErrors, QuestionValues } from "./validation";
import { useFormValidation } from "./useFormValidation";
import { useQuizContext } from "./useQuizContext";
import UnsavedChanges from "./UnsavedChanges";
import "./quiz.css";

type Proposal = Omit<QuestionValues, "position"> & { notion: string };
type Draft = { id: string; selected: boolean; values: Proposal };
type GeneratedQuestion = Omit<Proposal, "points"> & { points: number };
// The local AI runs in the background: the request answers 202 with a job that the page polls.
type GenerationJob = {
  id: string;
  status: "QUEUED" | "RUNNING" | "SUCCEEDED" | "FAILED";
  delivered: boolean;
  questions?: GeneratedQuestion[];
  error?: { code: string; message: string; status: number; fields: Record<string, string[]> };
};
const sleep = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));
type ImportPayload = {
  import_key: string;
  confirmed: true;
  questions: (Omit<Proposal, "points"> & { points: number })[];
};

export default function GenerateQuestions() {
  const { id } = useParams();
  const { data: quiz, error, loading } = useResource<Quiz>(`quizzes/${id}/`);
  if (loading) return <Loading />;
  if (!quiz) return <Alert error={error} />;
  if (quiz.status !== "DRAFT")
    return (
      <Alert error="Ce quiz est verrouillé. La génération est réservée aux brouillons." />
    );
  return <Generator key={quiz.id} quiz={quiz} />;
}

function Generator({ quiz }: { quiz: Quiz }) {
  const { base } = useQuizContext();
  const [inputs, setInputs] = useState({
    course_text: "",
    count: "3",
    level: quiz.level,
  });
  const [drafts, setDrafts] = useState<Draft[]>([]);
  const [busy, setBusy] = useState<"generate" | "import" | null>(null);
  const [elapsed, setElapsed] = useState(0);
  const alive = useRef(true);
  // Stops polling when the page is left (and survives the double mount of React's strict mode).
  useEffect(() => {
    alive.current = true;
    return () => void (alive.current = false);
  }, []);
  useEffect(() => {
    if (busy !== "generate") return;
    setElapsed(0);
    const timer = setInterval(() => setElapsed((value) => value + 1), 1000);
    return () => clearInterval(timer);
  }, [busy]);
  const [error, setError] = useState<unknown>();
  const [uncertain, setUncertain] = useState(false);
  const [added, setAdded] = useState(0);
  const locked = useRef(false),
    saved = useRef(false);
  const pendingImport = useRef<ImportPayload | null>(null);
  const generation = useFormValidation(() => {
    const issues: FieldErrors = {};
    if (!inputs.course_text.trim())
      issues.course_text = t("Collez le texte du cours.");
    else if (Array.from(inputs.course_text.trim()).length > 30000)
      issues.course_text = t("Limitez le cours à 30 000 caractères.");
    if (
      !/^[0-9]+$/.test(inputs.count) ||
      Number(inputs.count) < 1 ||
      Number(inputs.count) > 10
    )
      issues.count = t("Saisissez un nombre entier entre 1 et 10.");
    if (!(inputs.level in levels))
      issues.level = t("Sélectionnez un niveau valide.");
    return issues;
  }, inputs);
  const flatInputs = Object.fromEntries(
    drafts.flatMap((draft, index) =>
      Object.entries(draft.values).map(([field, value]) => [
        `questions.${index}.${field}`,
        value,
      ]),
    ),
  );
  const review = useFormValidation(
    () => {
      const issues: FieldErrors = {};
      if (!drafts.some((draft) => draft.selected))
        issues.selection = t("Sélectionnez au moins une proposition.");
      drafts.forEach((draft, index) => {
        if (!draft.selected) return;
        const errors = validateQuestion({ ...draft.values, position: "1" });
        if (!draft.values.notion.trim())
          errors.notion = t("La notion est obligatoire.");
        else if (Array.from(draft.values.notion.trim()).length > 200)
          errors.notion = t("Limitez la notion à 200 caractères.");
        if (Array.from(draft.values.explanation.trim()).length > 4000)
          errors.explanation = t("Limitez l’explication à 4 000 caractères.");
        for (const [field, message] of Object.entries(errors))
          issues[`questions.${index}.${field}`] = message;
      });
      return issues;
    },
    {
      ...flatInputs,
      selection: drafts
        .filter((draft) => draft.selected)
        .map((draft) => draft.id)
        .join(","),
    },
  );

  async function generate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (locked.current || drafts.length || uncertain) return;
    locked.current = true;
    setError(undefined);
    try {
      generation.check();
      setBusy("generate");
      const started = await api<GenerationJob | { questions: GeneratedQuestion[] }>(
        `quizzes/${quiz.id}/generate-questions/`,
        "POST",
        { ...inputs, count: Number(inputs.count) },
      );
      let questions = "questions" in started ? started.questions : undefined;
      if (!questions && "id" in started) {
        let job: GenerationJob = started;
        while (alive.current && !job.questions && job.status !== "FAILED") {
          await sleep(2000);
          job = await api<GenerationJob>(`quizzes/${quiz.id}/generate-questions/${job.id}/`);
        }
        if (!alive.current) return;
        if (job.status === "FAILED" && job.error)
          throw new ApiError(job.error.status || 503, job.error.message, job.error.fields, job.error.code);
        if (!job.questions?.length)
          throw new ApiError(410, "Ces propositions ont déjà été affichées. Relancez la génération.");
        questions = job.questions;
      }
      setDrafts(
        (questions || []).map((values) => ({
          id: crypto.randomUUID(),
          selected: true,
          values: { ...values, points: String(values.points) },
        })),
      );
      requestAnimationFrame(() =>
        document.getElementById("quiz-ai-review")?.focus(),
      );
    } catch (err) {
      setError(err);
      generation.serverErrors(err);
    } finally {
      setBusy(null);
      locked.current = false;
    }
  }

  async function confirm(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (locked.current || added) return;
    locked.current = true;
    setError(undefined);
    const retry = pendingImport.current !== null;
    try {
      if (!retry) {
        review.check();
        pendingImport.current = {
          import_key: crypto.randomUUID(),
          confirmed: true,
          questions: drafts
            .filter((draft) => draft.selected)
            .map((draft) => ({
              ...draft.values,
              points: Number(draft.values.points),
            })),
        };
      }
      setBusy("import");
      const result = await api<{ results: unknown[] }>(
        `quizzes/${quiz.id}/import-questions/`,
        "POST",
        pendingImport.current,
      );
      const count = result.results.length;
      saved.current = true;
      setAdded(count);
      setUncertain(false);
    } catch (err) {
      // A lost response may have committed. Retry the identical payload and key.
      const remoteError = pendingImport.current !== null;
      if (
        pendingImport.current &&
        !(err instanceof ApiError && err.status === 400 && !retry)
      )
        setUncertain(true);
      else pendingImport.current = null;
      if (err instanceof ApiError) {
        const selectedIndexes = drafts.flatMap((draft, index) =>
          draft.selected ? [index] : [],
        );
        const fields = Object.fromEntries(
          Object.entries(err.fields).map(([field, value]) => [
            remoteError
              ? field.replace(
                  /^questions\.(\d+)\./,
                  (_, index: string) =>
                    `questions.${selectedIndexes[Number(index)]}.`,
                )
              : field,
            value,
          ]),
        );
        review.serverErrors(
          new ApiError(err.status, err.message, fields, err.code),
        );
      }
      setError(err);
    } finally {
      setBusy(null);
      locked.current = false;
    }
  }

  function update(index: number, field: keyof Proposal, value: string) {
    setDrafts((current) =>
      current.map((draft, i) =>
        i === index
          ? { ...draft, values: { ...draft.values, [field]: value } }
          : draft,
      ),
    );
    setError(undefined);
  }
  const disabled = busy !== null || uncertain;
  return (
    <div className="quiz-module">
      <LanguageNotice />
      <UnsavedChanges
        dirty={Boolean(inputs.course_text.trim() || drafts.length)}
        ignore={saved}
      />
      <div className="page-heading">
        <div>
          <p className="eyebrow">{t("IA locale — Qwen3 via Ollama")}</p>
          <h1>{t("Générer des questions avec l’IA")}</h1>
          <p>{quiz.title}</p>
        </div>
        <Link className="text-button" to={`${base}/${quiz.id}`}>
          {t("Retour au quiz ")}
        </Link>
      </div>
      {added ? (
        <section className="panel">
          <h2>{t("Questions ajoutées au brouillon")}</h2>
          <Alert
            success={`${added} question${added > 1 ? "s" : ""} ajoutée${added > 1 ? "s" : ""}. Le quiz reste en brouillon.`}
          />
          <Link className="btn_one" to={`${base}/${quiz.id}`}>
            {t("Vérifier les questions du quiz ")}
          </Link>
        </section>
      ) : (
        <>
          <p className="notice">
            {t(
              "Le cours est traité par le serveur Ollama configuré. Vérifiez les propositions : aucune question n’est enregistrée avant votre confirmation et le quiz reste en brouillon. ",
            )}
          </p>
          <Alert error={error instanceof ApiError ? error.message : error} />
          <form
            ref={generation.formProps.formRef}
            noValidate
            onBlur={generation.formProps.onBlur}
            onSubmit={generate}
          >
            <fieldset disabled={disabled} className="panel quiz-ai-fields">
              <legend>{t("1. Le contenu du cours")}</legend>
              <p className="field-help">
                {t(
                  "Tous les champs sont obligatoires. Texte collé uniquement, 30 000 caractères maximum. ",
                )}
              </p>
              <Textarea
                label={t("Texte du cours")}
                name="course_text"
                required
                rows={9}
                maxLength={30000}
                value={inputs.course_text}
                onChange={(e) => {
                  setInputs((v) => ({ ...v, course_text: e.target.value }));
                  setError(undefined);
                }}
                error={generation.errors.course_text}
              />
              <div className="form-grid">
                <Field
                  label={t("Nombre de questions")}
                  name="count"
                  type="number"
                  min={1}
                  max={10}
                  step={1}
                  required
                  value={inputs.count}
                  onChange={(e) =>
                    setInputs((v) => ({ ...v, count: e.target.value }))
                  }
                  error={generation.errors.count}
                />
                <Select
                  label={t("Niveau")}
                  name="level"
                  required
                  value={inputs.level}
                  onChange={(e) =>
                    setInputs((v) => ({
                      ...v,
                      level: e.target.value as Quiz["level"],
                    }))
                  }
                  error={generation.errors.level}
                >
                  {Object.entries(levels).map(([value, label]) => (
                    <option key={value} value={value}>
                      {t(label)}
                    </option>
                  ))}
                </Select>
              </div>
              <button className="btn_one" disabled={drafts.length > 0}>
                {busy === "generate"
                  ? t("Génération en cours…")
                  : t("Générer les propositions")}
              </button>
              {drafts.length > 0 && (
                <p className="field-help">
                  {t(
                    "Ajoutez ou retirez les propositions actuelles avant une nouvelle génération. ",
                  )}
                </p>
              )}
            </fieldset>
          </form>
          {busy === "generate" && (
            <p role="status" className="notice">
              {t(
                "L’IA locale prépare les propositions. Rien n’est encore enregistré. La génération peut prendre quelques minutes. ",
              )}{" "}
              <span aria-hidden="true">({elapsed} s)</span>
            </p>
          )}
          {drafts.length > 0 && (
            <form
              ref={review.formProps.formRef}
              noValidate
              onBlur={review.formProps.onBlur}
              onSubmit={confirm}
            >
              <h2 id="quiz-ai-review" tabIndex={-1}>
                {t("2. Vérifier et sélectionner les propositions ")}
              </h2>
              <p>
                {t(
                  "Corrigez les champs avant confirmation. Les questions sélectionnées seront ajoutées à la fin du quiz, dans l’ordre affiché. ",
                )}
              </p>
              <fieldset disabled={disabled} className="quiz-ai-fields">
                <legend className="visually-hidden">
                  {t("Propositions de questions ")}
                </legend>
                {drafts.map((draft, index) => {
                  const field = (key: keyof Proposal) => ({
                    name: `questions.${index}.${key}`,
                    value: draft.values[key],
                    onChange: (e: { target: { value: string } }) =>
                      update(index, key, e.target.value),
                    error: review.errors[`questions.${index}.${key}`],
                    required: true,
                  });
                  return (
                    <section
                      className="panel"
                      key={draft.id}
                      aria-label={t("Proposition {0}", [index + 1])}
                    >
                      <div className="quiz-question-heading">
                        <h3>
                          {t("Proposition ")}
                          {index + 1}
                        </h3>
                        <button
                          type="button"
                          className="text-button"
                          aria-label={t("Retirer la proposition {0}", [
                            index + 1,
                          ])}
                          onClick={() =>
                            setDrafts((current) =>
                              current.filter((item) => item.id !== draft.id),
                            )
                          }
                        >
                          {t("Retirer ")}
                        </button>
                      </div>
                      <label className="quiz-answer-radio">
                        <input
                          type="checkbox"
                          name="selection"
                          checked={draft.selected}
                          aria-invalid={
                            review.errors.selection ? true : undefined
                          }
                          aria-describedby={
                            review.errors.selection
                              ? "quiz-ai-selection-error"
                              : undefined
                          }
                          onChange={(e) =>
                            setDrafts((current) =>
                              current.map((item) =>
                                item.id === draft.id
                                  ? { ...item, selected: e.target.checked }
                                  : item,
                              ),
                            )
                          }
                        />
                        {t(" Sélectionner la proposition {0}", [index + 1])}
                      </label>
                      <Textarea
                        label="Énoncé"
                        rows={3}
                        maxLength={2000}
                        {...field("statement")}
                      />
                      <div className="form-grid">
                        {(["a", "b", "c", "d"] as const).map((letter) => (
                          <Textarea
                            key={letter}
                            label={t("Proposition {0}", [letter.toUpperCase()])}
                            rows={2}
                            maxLength={500}
                            {...field(`choice_${letter}`)}
                          />
                        ))}
                      </div>
                      <div className="form-grid">
                        <Select
                          label={t("Bonne réponse")}
                          {...field("correct_answer")}
                        >
                          <option value="">{t("Sélectionner")}</option>
                          {["A", "B", "C", "D"].map((letter) => (
                            <option key={letter} value={letter}>
                              {letter}
                            </option>
                          ))}
                        </Select>
                        <Field
                          label={t("Points")}
                          type="number"
                          min={1}
                          max={10}
                          step={1}
                          {...field("points")}
                        />
                      </div>
                      <Textarea
                        label={t("Explication de correction")}
                        rows={3}
                        maxLength={4000}
                        {...field("explanation")}
                      />
                      <Field
                        label={t("Notion")}
                        maxLength={200}
                        {...field("notion")}
                      />
                    </section>
                  );
                })}
              </fieldset>
              {review.errors.selection && (
                <p
                  id="quiz-ai-selection-error"
                  role="alert"
                  className="notice notice-error"
                >
                  {review.errors.selection}
                </p>
              )}
              {uncertain && (
                <p role="status" className="notice">
                  {t(
                    "La confirmation de l’ajout est en attente. Réessayez sans modifier les propositions : la même confirmation ne créera pas de doublon. ",
                  )}
                </p>
              )}
              {busy === "import" && (
                <p role="status">{t("Ajout des questions sélectionnées…")}</p>
              )}
              <button className="btn_one" disabled={busy !== null}>
                {uncertain
                  ? t("Réessayer la confirmation")
                  : t("Ajouter les questions sélectionnées")}
              </button>
            </form>
          )}
        </>
      )}
    </div>
  );
}
