import { useEffect, useRef, useState } from "react";
import type { FormEvent } from "react";
import { api } from "../../api/client";
import { Alert, Modal } from "../../components/UI";
import type { AIJob, SelfQuizQuestion } from "../types";
import { engines } from "../types";

/** Training quiz written by the AI from the sheet: generated in the background, corrected at once. */
export default function SelfQuiz({ sheetId, onClose }: { sheetId: string; onClose: () => void }) {
  const [count, setCount] = useState(5);
  const [job, setJob] = useState<AIJob | null>(null);
  const [error, setError] = useState<unknown>();
  const [elapsed, setElapsed] = useState(0);
  const [index, setIndex] = useState(0);
  const [choice, setChoice] = useState<number | null>(null);
  const [checked, setChecked] = useState(false);
  const [score, setScore] = useState(0);
  const alive = useRef(true);
  useEffect(() => {
    alive.current = true;
    return () => void (alive.current = false);
  }, []);
  const running = job !== null && (job.status === "QUEUED" || job.status === "RUNNING");
  useEffect(() => {
    if (!running) return;
    setElapsed(0);
    const timer = setInterval(() => setElapsed((s) => s + 1), 1000);
    return () => clearInterval(timer);
  }, [running]);
  const questions: SelfQuizQuestion[] = job?.result?.questions || [];
  const question = questions[index];
  const finished = questions.length > 0 && index >= questions.length;

  async function start(event?: FormEvent) {
    event?.preventDefault();
    setError(undefined);
    setIndex(0);
    setChoice(null);
    setChecked(false);
    setScore(0);
    try {
      let current = await api<AIJob>(`sheets/${sheetId}/self-quiz/`, "POST", { count });
      setJob(current);
      while (alive.current && (current.status === "QUEUED" || current.status === "RUNNING")) {
        await new Promise((resolve) => setTimeout(resolve, 2000));
        current = await api<AIJob>(`ai/jobs/${current.id}/`);
        if (alive.current) setJob(current);
      }
      if (current.status === "FAILED") setError(new Error(current.error || "La génération du quiz a échoué."));
    } catch (err) {
      setError(err);
      setJob(null);
    }
  }

  function check(event: FormEvent) {
    event.preventDefault();
    if (choice === null || !question) return;
    setChecked(true);
    if (choice === question.answer) setScore((s) => s + 1);
  }

  function next() {
    setIndex((i) => i + 1);
    setChoice(null);
    setChecked(false);
  }

  return (
    <Modal title="Quiz d’entraînement" onClose={onClose}>
      <div className="self-quiz">
        <Alert error={error} />
        {!job || (job.status === "FAILED" && !questions.length) ? (
          <form onSubmit={start} className="self-quiz-start">
            <p>
              L’IA rédige des questions à partir de cette fiche uniquement, puis tu réponds et tu vois aussitôt la
              correction. Rien n’est noté ni enregistré dans tes résultats.
            </p>
            <fieldset className="self-quiz-count">
              <legend>Nombre de questions</legend>
              {[3, 5, 10].map((n) => (
                <label key={n}>
                  <input type="radio" name="count" value={n} checked={count === n} onChange={() => setCount(n)} /> {n}
                </label>
              ))}
            </fieldset>
            <button className="btn_one">
              <span className="ti-wand" aria-hidden="true" /> Préparer mon quiz
            </button>
          </form>
        ) : running ? (
          <p className="notice" role="status">
            L’IA prépare tes questions… <span aria-hidden="true">({elapsed} s)</span>
          </p>
        ) : finished ? (
          <div className="self-quiz-end" role="status">
            <p className="self-quiz-score">
              {score} / {questions.length}
            </p>
            <p>
              {score === questions.length
                ? "Parfait : cette fiche est maîtrisée."
                : score >= questions.length / 2
                  ? "Bon travail. Relis les notions manquées puis recommence."
                  : "Relis la fiche, puis retente le quiz : chaque essai propose de nouvelles questions."}
            </p>
            <div className="self-quiz-actions">
              <button className="btn_one" onClick={() => start()}>
                Nouveau quiz
              </button>
              <button className="sheets-ghost-button" onClick={onClose}>
                Revenir à la fiche
              </button>
            </div>
          </div>
        ) : question ? (
          <form onSubmit={check}>
            <p className="self-quiz-progress">
              Question {index + 1} sur {questions.length} · {score} bonne{score > 1 ? "s" : ""} réponse{score > 1 ? "s" : ""}
            </p>
            <fieldset className="self-quiz-question" disabled={checked}>
              <legend>{question.question}</legend>
              {question.choices.map((text, i) => (
                <label
                  key={text}
                  className={
                    checked ? (i === question.answer ? "is-right" : i === choice ? "is-wrong" : "") : ""
                  }
                >
                  <input type="radio" name="choice" checked={choice === i} onChange={() => setChoice(i)} />
                  <span>{text}</span>
                </label>
              ))}
            </fieldset>
            <div aria-live="polite">
              {checked && (
                <p className={"notice " + (choice === question.answer ? "" : "notice-error")}>
                  <strong>{choice === question.answer ? "Bonne réponse." : `Réponse attendue : ${question.choices[question.answer]}.`}</strong>{" "}
                  {question.explanation}
                </p>
              )}
            </div>
            {checked ? (
              <button type="button" className="btn_one" onClick={next}>
                {index + 1 < questions.length ? "Question suivante" : "Voir mon score"}
              </button>
            ) : (
              <button className="btn_one" disabled={choice === null}>
                Valider
              </button>
            )}
            <p className="field-help">
              Questions rédigées par {engines[job?.engine || ""] || job?.engine} à partir de la fiche : en cas de doute, la fiche fait foi.
            </p>
          </form>
        ) : null}
      </div>
    </Modal>
  );
}
