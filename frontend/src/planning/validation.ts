import { useRef, useState } from "react";
import type { ChangeEvent } from "react";
import { ApiError, iso } from "../api/client";
import { daySpan, isDay, shortDate, today } from "./format";
import type { Slot } from "./types";

export type FieldErrors = Record<string, string>;
export const TITLE_MAX_LENGTH = 120;
type Body = Record<string, unknown>;

const filled = (errors: FieldErrors): FieldErrors =>
  Object.fromEntries(Object.entries(errors).filter(([, value]) => value));
export function minutesOf(value: string) {
  const match = /^(\d{2}):(\d{2})/.exec(value);
  return match ? Number(match[1]) * 60 + Number(match[2]) : NaN;
}
// datetime-local values only; anything else would make iso() throw.
export const isoOrEmpty = (value: string) =>
  /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$/.test(value) ? iso(value) : "";
export const integerOrText = (value: string) =>
  /^[0-9]+$/.test(value.trim()) ? Number(value.trim()) : value.trim();
function textError(
  value: string,
  label: string,
  max: number,
  required = false,
) {
  if (required && !value.trim()) return `${label} est obligatoire.`;
  if (Array.from(value.trim()).length > max)
    return `${label} doit contenir au maximum ${max} caractères.`;
  return "";
}
function rangeErrors(start: number, end: number, min: number, max: number) {
  if (end <= start) return "La fin doit être après le début.";
  if (end - start < min || end - start > max)
    return `La durée doit être comprise entre ${min} min et ${max / 60} h.`;
  return "";
}

export const validateTitle = (title: string) =>
  filled({ title: textError(title, "Le titre", TITLE_MAX_LENGTH, true) });

export function validateGoal(values: {
  title: string;
  description: string;
  target_date: string;
  estimated_hours: string;
}) {
  const hours = integerOrText(values.estimated_hours);
  return filled({
    title: textError(values.title, "Le titre", TITLE_MAX_LENGTH, true),
    description: textError(values.description, "La description", 1000),
    target_date:
      values.target_date && !isDay(values.target_date)
        ? "Saisissez une date valide."
        : "",
    estimated_hours:
      typeof hours === "number" && hours >= 1 && hours <= 200
        ? ""
        : "Saisissez un nombre entier d’heures entre 1 et 200.",
  });
}

export function validateDeadline(
  values: { title: string; kind: string; due_at: string; notes: string },
  mustBeFuture: boolean,
) {
  const due = isoOrEmpty(values.due_at);
  return filled({
    title: textError(values.title, "Le titre", TITLE_MAX_LENGTH, true),
    kind: values.kind ? "" : "Sélectionnez un type d’échéance.",
    due_at: !due
      ? "La date et l’heure de l’échéance sont obligatoires."
      : mustBeFuture && Date.parse(due) <= Date.now()
        ? "Choisissez une date et une heure à venir."
        : "",
    notes: textError(values.notes, "Les notes", 500),
  });
}

export function validateSlot(
  values: { weekday: string; start_time: string; end_time: string },
  others: Slot[],
) {
  const start = minutesOf(values.start_time),
    end = minutesOf(values.end_time);
  const quarter = (value: number, label: string) =>
    Number.isNaN(value)
      ? `${label} est obligatoire.`
      : value % 15
        ? "Choisissez un quart d’heure : 00, 15, 30 ou 45 minutes."
        : "";
  const errors: FieldErrors = {
    weekday: /^[0-6]$/.test(values.weekday) ? "" : "Sélectionnez un jour.",
    start_time: quarter(start, "L’heure de début"),
    end_time: quarter(end, "L’heure de fin"),
  };
  if (!errors.start_time && !errors.end_time) {
    errors.end_time = rangeErrors(start, end, 30, 360);
    if (
      !errors.end_time &&
      others.some(
        (slot) =>
          slot.weekday === Number(values.weekday) &&
          start < minutesOf(slot.end_time) &&
          minutesOf(slot.start_time) < end,
      )
    )
      errors.start_time = "Ce créneau chevauche un autre créneau du même jour.";
  }
  return filled(errors);
}

export function validateGeneration(values: {
  title: string;
  start_date: string;
  end_date: string;
}) {
  const errors: FieldErrors = {
    title: textError(values.title, "Le titre", TITLE_MAX_LENGTH),
    start_date: !isDay(values.start_date)
      ? "La date de début est obligatoire."
      : values.start_date < today()
        ? "Le planning ne peut pas commencer dans le passé."
        : "",
    end_date: !isDay(values.end_date) ? "La date de fin est obligatoire." : "",
  };
  if (isDay(values.start_date) && !errors.end_date) {
    const span = daySpan(values.start_date, values.end_date);
    if (span < 1)
      errors.end_date = "La fin doit tomber le jour du début ou après.";
    else if (span > 28)
      errors.end_date = "Un planning couvre au maximum 28 jours.";
  }
  return filled(errors);
}

export function validateTask(
  values: {
    title: string;
    description: string;
    day: string;
    starts_at: string;
    ends_at: string;
  },
  plan: { start_date: string; end_date: string },
) {
  const start = minutesOf(values.starts_at),
    end = minutesOf(values.ends_at);
  const errors: FieldErrors = {
    title: textError(values.title, "Le titre", TITLE_MAX_LENGTH, true),
    description: textError(values.description, "La description", 1000),
    day: !isDay(values.day)
      ? "Le jour est obligatoire."
      : values.day < plan.start_date || values.day > plan.end_date
        ? `Choisissez un jour du ${shortDate(plan.start_date)} au ${shortDate(plan.end_date)}.`
        : "",
    starts_at: Number.isNaN(start) ? "L’heure de début est obligatoire." : "",
    ends_at: Number.isNaN(end) ? "L’heure de fin est obligatoire." : "",
  };
  if (!errors.starts_at && !errors.ends_at)
    errors.ends_at = rangeErrors(start, end, 15, 240);
  return filled(errors);
}

// PATCH bodies only carry what the user changed, so unchanged legacy values are never re-validated.
export const changes = (body: Body, initial: Body) =>
  Object.fromEntries(
    Object.entries(body).filter(
      ([key, value]) => JSON.stringify(value) !== JSON.stringify(initial[key]),
    ),
  );
export const compact = (body: Body) =>
  Object.fromEntries(
    Object.entries(body).filter(([, value]) => value !== null && value !== ""),
  );

export function usePlanningForm<T extends Record<string, string>>(start: T) {
  const [values, setValues] = useState(start),
    [initial] = useState(start),
    [errors, setErrors] = useState<FieldErrors>({});
  const formRef = useRef<HTMLFormElement>(null);
  function change(name: keyof T & string) {
    return (
      event: ChangeEvent<
        HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement
      >,
    ) => {
      const value = event.target.value;
      setValues((current) => ({ ...current, [name]: value }));
      clear(name);
    };
  }
  function show(next: FieldErrors) {
    setErrors(next);
    requestAnimationFrame(() =>
      formRef.current
        ?.querySelector<HTMLElement>('[aria-invalid="true"]')
        ?.focus(),
    );
  }
  async function submit<T>(
    issues: FieldErrors,
    request: () => Promise<T>,
  ): Promise<T> {
    if (Object.keys(issues).length) {
      show(issues);
      throw new ApiError(400, "Veuillez corriger les champs indiqués.", issues);
    }
    setErrors({});
    try {
      return await request();
    } catch (error) {
      if (error instanceof ApiError)
        show(
          Object.fromEntries(
            Object.entries(error.fields).map(([field, value]) => [
              field,
              Array.isArray(value) ? value.join(" ") : String(value),
            ]),
          ),
        );
      throw error;
    }
  }
  function clear(name: string) {
    if (errors[name])
      setErrors((current) =>
        Object.fromEntries(
          Object.entries(current).filter(([field]) => field !== name),
        ),
      );
  }
  return { values, initial, errors, formRef, change, submit };
}
