import { localDateTime } from "../api/client";
import type { Task } from "./types";

const zone = "Africa/Tunis";
// A calendar date has no zone: midday keeps it on the same day in Tunis.
const calendar = (day: string) => new Date(day + "T12:00:00+01:00");
const capitalize = (text: string) =>
  text.charAt(0).toUpperCase() + text.slice(1);
const decimal = new Intl.NumberFormat("fr-FR", { maximumFractionDigits: 1 });

export const isDay = (value: string) => /^\d{4}-\d{2}-\d{2}$/.test(value);
export const dayKey = (value: string) => localDateTime(value).slice(0, 10);
export const time = (value: string) => localDateTime(value).slice(11, 16);
export const timeRange = (start: string, end: string) =>
  `${time(start)} – ${time(end)}`;
export const today = () => dayKey(new Date().toISOString());
export function addDays(day: string, days: number) {
  const value = new Date(day + "T00:00:00Z");
  value.setUTCDate(value.getUTCDate() + days);
  return value.toISOString().slice(0, 10);
}
export const daySpan = (start: string, end: string) =>
  Math.round(
    (Date.parse(end + "T00:00:00Z") - Date.parse(start + "T00:00:00Z")) /
      86400000,
  ) + 1;
export const dayLabel = (day: string) =>
  capitalize(
    new Intl.DateTimeFormat("fr-FR", {
      weekday: "long",
      day: "numeric",
      month: "long",
      timeZone: zone,
    }).format(calendar(day)),
  );
export const shortDate = (day: string) =>
  new Intl.DateTimeFormat("fr-FR", {
    dateStyle: "medium",
    timeZone: zone,
  }).format(calendar(day));
export const period = (start: string, end: string) =>
  `Du ${shortDate(start)} au ${shortDate(end)}`;
export function duration(minutes: number) {
  const total = Math.max(0, Math.round(minutes));
  if (total < 60) return `${total} min`;
  const rest = total % 60;
  return `${Math.floor(total / 60)} h${rest ? " " + String(rest).padStart(2, "0") : ""}`;
}
export const plural = (count: number, singular: string, several: string) =>
  `${count} ${count > 1 ? several : singular}`;
export const percent = (value: number | null) =>
  value === null ? "Non calculable" : decimal.format(value) + " %";
export const seconds = (milliseconds: number) =>
  decimal.format(milliseconds / 1000) + " s";
export const count = (value: number) =>
  new Intl.NumberFormat("fr-FR").format(value);
export const fullName = (person: { first_name: string; last_name: string }) =>
  `${person.first_name} ${person.last_name}`.trim();
export const paragraphs = (text: string) =>
  text
    .split(/\n\s*\n/)
    .map((part) => part.trim())
    .filter(Boolean);
export function groupByDay(tasks: Task[]) {
  const days = new Map<string, Task[]>();
  for (const task of [...tasks].sort(
    (a, b) => Date.parse(a.starts_at) - Date.parse(b.starts_at),
  )) {
    const key = dayKey(task.starts_at);
    days.set(key, [...(days.get(key) || []), task]);
  }
  return [...days.entries()];
}
