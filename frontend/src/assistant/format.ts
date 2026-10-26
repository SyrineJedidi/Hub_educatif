import type { Citation, Person, Review } from "./types";
import { reasons } from "./types";

const number = (value: number, digits = 0) =>
  new Intl.NumberFormat("fr-FR", { maximumFractionDigits: digits }).format(
    value,
  );
export const count = (value: number | null | undefined) =>
  value == null ? "—" : number(value);
export function clock(seconds: number) {
  const total = Math.max(0, Math.floor(seconds));
  const pad = (value: number) => String(value).padStart(2, "0");
  const hours = Math.floor(total / 3600),
    minutes = Math.floor((total % 3600) / 60);
  return (
    (hours ? hours + ":" + pad(minutes) : pad(minutes)) + ":" + pad(total % 60)
  );
}
export const ratio = (value: number | null | undefined) =>
  value == null ? "Non calculable" : number(value * 100, 1) + " %";
export const duration = (ms: number | null | undefined) =>
  ms == null ? "Non calculable" : number(ms / 1000, 1) + " s";
export const plural = (value: number, one: string, many: string) =>
  number(value) + " " + (Math.abs(value) >= 2 ? many : one);
export const reasonLabels = (review: Review) =>
  review.reason_labels?.length
    ? review.reason_labels
    : review.reasons.map((reason) => reasons[reason] || reason);
export const personName = (person: Person | null | undefined) =>
  person ? `${person.first_name} ${person.last_name}`.trim() : "";
export const time = (value: string) =>
  new Intl.DateTimeFormat("fr-FR", {
    timeStyle: "short",
    timeZone: "Africa/Tunis",
  }).format(new Date(value));
export const day = (value: string) =>
  new Intl.DateTimeFormat("fr-FR", {
    dateStyle: "medium",
    timeZone: value.length === 10 ? "UTC" : "Africa/Tunis",
  }).format(new Date(value));
// YYYY-MM-DD in Tunis, `offset` days from today.
export function tunisDate(offset = 0) {
  return new Intl.DateTimeFormat("sv-SE", {
    timeZone: "Africa/Tunis",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(new Date(Date.now() + offset * 86400000));
}
export function location(citation: Citation) {
  if (citation.page) return "page " + citation.page;
  if (citation.start_seconds != null)
    return "à " + clock(citation.start_seconds);
  return "";
}
// Only same-origin application paths are rendered as links. The browser's own parser decides,
// because it reads "/\host" or a tab inside "//host" as a link to another site.
export function internalUrl(url: string) {
  if (!url.startsWith("/")) return "";
  try {
    const parsed = new URL(url, window.location.origin);
    return parsed.origin === window.location.origin
      ? parsed.pathname + parsed.search + parsed.hash
      : "";
  } catch {
    return "";
  }
}
// Emails and phone-like numbers of a student's text, masked in a draft the teacher still rereads before publishing it.
export const maskContacts = (text: string) =>
  text
    .replace(/[\w.+-]+@[\w-]+(\.[\w-]+)+/g, "[adresse]")
    .replace(/\+?\d[\d .-]{6,}\d/g, "[numéro]");
export function plainText(text: string) {
  return text
    .replace(/\[S(\d+)(?:\s*[,;]\s*S?\d+)*\]/g, "")
    .replace(/\*\*|`/g, "")
    .replace(/^\s*[-*•]\s+/gm, "")
    .replace(/\s+/g, " ")
    .trim();
}
export function excerpt(text: string, length = 300) {
  const plain = plainText(text);
  if (plain.length <= length) return plain;
  const cut = plain.slice(0, length);
  const space = cut.lastIndexOf(" ");
  return (space > length / 2 ? cut.slice(0, space) : cut) + "…";
}
export function newClientId() {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    try {
      return crypto.randomUUID();
    } catch {
      // randomUUID exists but throws outside secure contexts on some browsers.
    }
  }
  const bytes = new Uint8Array(16);
  if (typeof crypto !== "undefined" && crypto.getRandomValues)
    crypto.getRandomValues(bytes);
  else for (let i = 0; i < 16; i++) bytes[i] = Math.floor(Math.random() * 256);
  bytes[6] = (bytes[6] & 0x0f) | 0x40;
  bytes[8] = (bytes[8] & 0x3f) | 0x80;
  const hex = Array.from(bytes, (b) => b.toString(16).padStart(2, "0"));
  return [
    hex.slice(0, 4).join(""),
    hex.slice(4, 6).join(""),
    hex.slice(6, 8).join(""),
    hex.slice(8, 10).join(""),
    hex.slice(10).join(""),
  ].join("-");
}
