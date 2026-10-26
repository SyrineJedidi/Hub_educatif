import { useRef, useState } from "react";
import { api, ApiError } from "../api/client";
import type { Attempt, Choice, SavedAnswer } from "./attemptTypes";

interface AnswerState {
  choice: Choice;
  savedChoice?: Choice;
  revision: number;
  state: "pending" | "saving" | "saved" | "error";
  error?: string;
}

export function useAnswerQueue(
  attempt: Attempt,
  onClosed: () => Promise<void>,
) {
  const initial = Object.fromEntries(
    attempt.answers.map((a) => [
      a.question_id,
      {
        choice: a.selected_choice,
        savedChoice: a.selected_choice,
        revision: a.revision,
        state: "saved" as const,
      },
    ]),
  );
  const records = useRef<Record<string, AnswerState>>(initial);
  const [answers, setAnswers] = useState(records.current);
  const running = useRef<Promise<void> | null>(null);
  const inFlight = useRef<string | null>(null);
  const frozen = useRef(false);
  const [conflict, setConflict] = useState(false);
  const conflictRef = useRef(false);
  function emit() {
    setAnswers({ ...records.current });
  }
  function dirty() {
    return Object.values(records.current).some(
      (a) => a.state !== "saved" || a.choice !== a.savedChoice,
    );
  }

  function drain(): Promise<void> {
    if (running.current) return running.current;
    const work = async () => {
      while (!conflictRef.current) {
        const next = Object.entries(records.current).find(
          ([, a]) => a.state !== "saved" || a.choice !== a.savedChoice,
        );
        if (!next) break;
        const [id, entry] = next;
        const selected = entry.choice;
        inFlight.current = id;
        entry.state = "saving";
        entry.error = undefined;
        emit();
        try {
          const saved = await api<SavedAnswer>(
            `student/attempts/${attempt.id}/answers/${id}/`,
            "PUT",
            {
              selected_choice: selected,
              expected_revision: entry.revision,
            },
          );
          // Preserve any newer local selection made while this request was running.
          entry.savedChoice = saved.selected_choice;
          entry.revision = saved.revision;
          inFlight.current = null;
          entry.state =
            entry.choice === entry.savedChoice ? "saved" : "pending";
          emit();
        } catch (error) {
          inFlight.current = null;
          entry.state = "error";
          entry.error =
            error instanceof Error
              ? error.message
              : "La réponse n’a pas pu être enregistrée.";
          if (error instanceof ApiError && error.code === "answer_conflict") {
            conflictRef.current = true;
            setConflict(true);
          }
          emit();
          if (error instanceof ApiError && error.code === "attempt_closed")
            await onClosed();
          break;
        }
      }
    };
    running.current = work().finally(() => {
      running.current = null;
    });
    return running.current;
  }

  function select(id: string, choice: Choice) {
    if (frozen.current || conflictRef.current) return;
    const entry = records.current[id];
    records.current[id] = entry
      ? Object.assign(entry, {
          choice,
          state:
            inFlight.current === id ||
            entry.state === "error" ||
            choice !== entry.savedChoice
              ? "pending"
              : "saved",
        })
      : { choice, revision: 0, state: "pending" };
    emit();
    void drain();
  }
  async function flush() {
    await drain();
    if (dirty() || conflictRef.current)
      throw new ApiError(
        409,
        "Certaines réponses ne sont pas synchronisées. La tentative n’a pas été soumise. Réessayez l’enregistrement ou rechargez les réponses en cas de conflit.",
      );
    return Object.fromEntries(
      Object.entries(records.current)
        .filter(([, a]) => a.savedChoice)
        .map(([id, a]) => [id, a.revision]),
    );
  }
  return {
    answers,
    dirty: dirty(),
    conflict,
    select,
    retry: drain,
    flush,
    freeze: (value: boolean) => {
      frozen.current = value;
    },
  };
}
