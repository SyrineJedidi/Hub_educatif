import { t } from "./i18n";
import type { Group, User } from "../api/types";

export type FieldErrors = Record<string, string>;
export const MAX_INTEGER = 2147483647;
export const QUIZ_TITLE_MAX_LENGTH = 50;
export function duplicateTitle(title: string) {
  const suffix = t(" (copie)");
  return (
    Array.from(title)
      .slice(0, QUIZ_TITLE_MAX_LENGTH - suffix.length)
      .join("") + suffix
  );
}

function textError(
  value: string,
  label: string,
  max?: number,
  required = true,
) {
  if (required && !value.trim()) return t("{0} est obligatoire.", [label]);
  if (max && Array.from(value.trim()).length > max)
    return t("{0} doit contenir au maximum {1} caractères.", [label, max]);
  return "";
}

function integerError(value: string, label: string, max: number) {
  if (!value.trim()) return t("{0} est obligatoire.", [label]);
  if (!/^[0-9]+$/.test(value.trim()))
    return t(
      "{0} doit être un nombre entier, sans décimale ni notation scientifique.",
      [label],
    );
  const number = Number(value);
  if (!Number.isSafeInteger(number) || number < 1 || number > max)
    return t("Saisissez un entier compris entre 1 et {0}.", [max]);
  return "";
}

function nonEmptyErrors(errors: FieldErrors): FieldErrors {
  return Object.fromEntries(
    Object.entries(errors).filter(([, value]) => value),
  );
}

export function validateQuiz(
  values: {
    title: string;
    description: string;
    teacher: string;
    group: string;
    level: string;
    durationMode: string;
    duration: string;
    attempts: string;
    opens_at?: string;
    closes_at?: string;
  },
  groups: Group[],
  teachers: User[],
  admin: boolean,
): FieldErrors {
  const group = groups.find((item) => item.id === values.group);
  const errors: FieldErrors = {
    title: textError(values.title, t("Le titre"), QUIZ_TITLE_MAX_LENGTH),
    description: textError(values.description, t("La description"), 2000),
    level: ["EASY", "MEDIUM", "HARD"].includes(values.level)
      ? ""
      : t("Sélectionnez un niveau valide."),
    learning_group_id:
      group &&
      !group.archived &&
      (!admin || group.teacher_id === values.teacher)
        ? ""
        : t("Sélectionnez un groupe actif affecté à l’enseignant."),
    max_attempts: integerError(
      values.attempts,
      t("Le nombre de tentatives"),
      10,
    ),
    duration_mode: ["limited", "unlimited"].includes(values.durationMode)
      ? ""
      : t("Choisissez une durée limitée ou sans limite de temps."),
    duration_minutes:
      values.durationMode === "limited"
        ? integerError(values.duration, t("La durée en minutes"), MAX_INTEGER)
        : "",
  };
  if (admin)
    errors.teacher_id = teachers.some(
      (teacher) =>
        teacher.id === values.teacher &&
        teacher.is_active &&
        teacher.role === "TEACHER",
    )
      ? ""
      : t("Sélectionnez un enseignant actif.");
  const dates = [values.opens_at, values.closes_at];
  dates.forEach((value, index) => {
    if (value && !Number.isFinite(Date.parse(value + ":00+01:00")))
      errors[index ? "closes_at" : "opens_at"] = t(
        "Saisissez une date valide.",
      );
  });
  if (
    values.opens_at &&
    values.closes_at &&
    values.opens_at >= values.closes_at
  )
    errors.closes_at = t("La fermeture doit être postérieure à l’ouverture.");
  return nonEmptyErrors(errors);
}

export interface QuestionValues {
  statement: string;
  choice_a: string;
  choice_b: string;
  choice_c: string;
  choice_d: string;
  correct_answer: string;
  explanation: string;
  points: string;
  position: string;
}

export function validateQuestion(values: QuestionValues): FieldErrors {
  const errors: FieldErrors = {
    statement: textError(values.statement, t("L’énoncé"), 2000),
    explanation: textError(
      values.explanation,
      t("L’explication de correction"),
    ),
    points: integerError(values.points, t("Le nombre de points"), 10),
    position: integerError(values.position, t("La position"), MAX_INTEGER),
    correct_answer: ["A", "B", "C", "D"].includes(values.correct_answer)
      ? ""
      : t("Sélectionnez exactement une bonne réponse parmi A, B, C et D."),
  };
  const choices = new Map<string, string>();
  for (const letter of ["a", "b", "c", "d"] as const) {
    const field = `choice_${letter}` as const;
    const value = values[field].trim().replace(/\s+/gu, " ").toLowerCase();
    errors[field] = textError(
      values[field],
      t("La proposition {0}", [letter.toUpperCase()]),
      500,
    );
    if (value && choices.has(value))
      errors[field] = t(
        "Cette proposition est identique à la proposition {0} après normalisation des espaces et de la casse.",
        [choices.get(value)],
      );
    else choices.set(value, letter.toUpperCase());
  }
  return nonEmptyErrors(errors);
}
