import type { Person, Resource } from "./types";

const number = (value: number, digits = 0) =>
  new Intl.NumberFormat("fr-FR", { maximumFractionDigits: digits }).format(
    value,
  );
export function fileSize(bytes: number) {
  if (bytes < 1024 * 1024)
    return number(Math.max(1, Math.round(bytes / 1024))) + " Ko";
  return number(bytes / (1024 * 1024), 1) + " Mo";
}
export function clock(seconds: number) {
  const total = Math.max(0, Math.floor(seconds));
  const pad = (value: number) => String(value).padStart(2, "0");
  const hours = Math.floor(total / 3600),
    minutes = Math.floor((total % 3600) / 60);
  return (
    (hours ? hours + ":" + pad(minutes) : pad(minutes)) + ":" + pad(total % 60)
  );
}
export function spokenDuration(seconds: number) {
  const total = Math.max(0, Math.floor(seconds));
  const parts = (
    [
      [Math.floor(total / 3600), "h"],
      [Math.floor((total % 3600) / 60), "min"],
      [total % 60, "s"],
    ] as [number, string][]
  ).filter(([value]) => value > 0);
  return parts.length
    ? parts.map(([value, unit]) => value + " " + unit).join(" ")
    : "0 s";
}
export const percent = (value: number | null | undefined) =>
  value == null ? "Non calculable" : number(value, 1) + " %";
export const seconds = (value: number) => number(value, 1) + " s";
export const plural = (count: number, one: string, many: string) =>
  count + " " + (Math.abs(count) >= 2 ? many : one);
export const personName = (person: Person) =>
  `${person.first_name} ${person.last_name}`.trim();
export function resourceFacts(resource: Resource) {
  const facts = [fileSize(resource.size)];
  if (resource.page_count)
    facts.push(plural(resource.page_count, "page", "pages"));
  if (resource.duration_seconds) facts.push(clock(resource.duration_seconds));
  return facts.join(" · ");
}
export function titleFromFile(name: string) {
  return Array.from(
    name
      .replace(/\.[^.]+$/u, "")
      .replace(/_+/gu, " ")
      .replace(/\s+/gu, " ")
      .trim(),
  )
    .slice(0, 120)
    .join("");
}
