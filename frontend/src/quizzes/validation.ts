import type { Group, User } from "../api/types";

export type FieldErrors = Record<string, string>;
export const MAX_INTEGER = 2147483647;
export const QUIZ_TITLE_MAX_LENGTH = 50;
export function duplicateTitle(title: string) {
  const suffix = " (copie)";
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
  if (required && !value.trim()) return `${label} est obligatoire.`;
  if (max && Array.from(value.trim()).length > max)
    return `${label} doit contenir au maximum ${max} caractères.`;
  return "";
}

function integerError(value: string, label: string, max: number) {
  if (!value.trim()) return `${label} est obligatoire.`;
  if (!/^[0-9]+$/.test(value.trim()))
    return `${label} doit être un nombre entier, sans décimale ni notation scientifique.`;
  const number = Number(value);
  if (!Number.isSafeInteger(number) || number < 1 || number > max)
    return `Saisissez un entier compris entre 1 et ${max}.`;
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
  },
  groups: Group[],
  teachers: User[],
  admin: boolean,
): FieldErrors {
  const group = groups.find((item) => item.id === values.group);
  const errors: FieldErrors = {
    title: textError(values.title, "Le titre", QUIZ_TITLE_MAX_LENGTH),
    description: textError(values.description, "La description", 2000),
    level: ["EASY", "MEDIUM", "HARD"].includes(values.level)
      ? ""
      : "Sélectionnez un niveau valide.",
    learning_group_id:
      group &&
      !group.archived &&
      (!admin || group.teacher_id === values.teacher)
        ? ""
        : "Sélectionnez un groupe actif affecté à l’enseignant.",
    max_attempts: integerError(values.attempts, "Le nombre de tentatives", 10),
    duration_mode: ["limited", "unlimited"].includes(values.durationMode)
      ? ""
      : "Choisissez une durée limitée ou sans limite de temps.",
    duration_minutes:
      values.durationMode === "limited"
        ? integerError(values.duration, "La durée en minutes", MAX_INTEGER)
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
      : "Sélectionnez un enseignant actif.";
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
    statement: textError(values.statement, "L’énoncé", 2000),
    explanation: textError(values.explanation, "L’explication de correction"),
    points: integerError(values.points, "Le nombre de points", 10),
    position: integerError(values.position, "La position", MAX_INTEGER),
    correct_answer: ["A", "B", "C", "D"].includes(values.correct_answer)
      ? ""
      : "Sélectionnez exactement une bonne réponse parmi A, B, C et D.",
  };
  const choices = new Map<string, string>();
  for (const letter of ["a", "b", "c", "d"] as const) {
    const field = `choice_${letter}` as const;
    const value = values[field].trim().replace(/\s+/gu, " ").toLowerCase();
    errors[field] = textError(
      values[field],
      `La proposition ${letter.toUpperCase()}`,
      500,
    );
    if (value && choices.has(value))
      errors[field] =
        `Cette proposition est identique à la proposition ${choices.get(value)} après normalisation des espaces et de la casse.`;
    else choices.set(value, letter.toUpperCase());
  }
  return nonEmptyErrors(errors);
}
