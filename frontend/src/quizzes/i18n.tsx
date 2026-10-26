import { useSyncExternalStore } from "react";
import { messages } from "./messages";
export type QuizLanguage = "fr" | "en" | "ar";
let language: QuizLanguage = "fr";
try {
  const saved = localStorage.getItem("quiz-interface-language");
  if (saved === "en" || saved === "ar") language = saved;
} catch {
  /* storage may be unavailable */
}
const listeners = new Set<() => void>();
const subscribe = (listener: () => void) => {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
};
export const quizLanguage = () => language;
export const locale = () =>
  language === "ar" ? "ar-TN-u-nu-arab" : language === "en" ? "en-GB" : "fr-FR";
export const n = (value: number | null | undefined) =>
  value == null
    ? "—"
    : new Intl.NumberFormat(locale(), { maximumFractionDigits: 2 }).format(
        value,
      );
export function setQuizLanguage(value: QuizLanguage) {
  language = value;
  try {
    localStorage.setItem("quiz-interface-language", value);
  } catch {
    /* optional storage */
  }
  listeners.forEach((listener) => listener());
}
export function useQuizLanguage() {
  return useSyncExternalStore(subscribe, quizLanguage, quizLanguage);
}
const normalize = (value: string) => value.replace(/\s+/g, " ").trim();
// Form errors may already be translated when they are stored in React state.
// Resolve fixed messages back to their key so they follow later language changes.
const messageKeys = new Map<string, string>();
for (const [key, translations] of Object.entries(messages)) {
  if (!/\{\d+\}/.test(key)) {
    for (const translation of translations) {
      messageKeys.set(normalize(translation), key);
    }
  }
}
function interpolate(value: string, args: unknown[]) {
  return value.replace(/\{(\d+)\}/g, (_, index) => {
    const arg = args[Number(index)];
    return typeof arg === "number" ? n(arg) : String(arg ?? "");
  });
}
const patterns = Object.keys(messages)
  .filter((key) => /\{\d+\}/.test(key))
  .map((key) => ({
    key,
    regex: new RegExp(
      "^" +
        key
          .split(/(\{\d+\})/)
          .map((part) =>
            /^\{\d+\}$/.test(part)
              ? "(.+?)"
              : part.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"),
          )
          .join("") +
        "$",
    ),
  }));
export function t(value: string, args?: unknown[]): string {
  const originalKey = normalize(value);
  const key = messages[originalKey]
    ? originalKey
    : messageKeys.get(originalKey) || originalKey;
  const source = key === originalKey ? value : key;
  if (language === "fr") return args ? interpolate(source, args) : source;
  const index = language === "en" ? 0 : 1;
  let translated = messages[key]?.[index];
  let values = args;
  if (!translated && !args) {
    for (const pattern of patterns) {
      const match = key.match(pattern.regex);
      if (match) {
        translated = messages[pattern.key][index];
        values = match
          .slice(1)
          .map((part, i) =>
            /^\d+(?:\.\d+)?$/.test(part)
              ? Number(part)
              : i === 0 && pattern.key.startsWith("{0} ")
                ? t(part)
                : part,
          );
        break;
      }
    }
  }
  if (!translated) return args ? interpolate(value, args) : value;
  return (
    (value.match(/^\s*/)?.[0] || "") +
    interpolate(translated, values || []) +
    (value.match(/\s*$/)?.[0] || "")
  );
}
export function LanguageSelect() {
  const current = useQuizLanguage();
  return (
    <label className="quiz-language">
      <span>{t("Langue de l’interface")}</span>
      <select
        aria-label={t("Langue de l’interface")}
        value={current}
        onChange={(event) =>
          setQuizLanguage(event.target.value as QuizLanguage)
        }
      >
        <option value="fr">Français</option>
        <option value="en">English</option>
        <option value="ar">العربية</option>
      </select>
    </label>
  );
}
export function publicationReason(reason: string) {
  const question = /^Question (\d+), ([^:]+) : (.*)$/s.exec(reason);
  if (question) {
    const label = question[2].trim();
    const labels: Record<string, string> = {
      statement: "Énoncé",
      énoncé: "Énoncé",
      explanation: "Explication",
      "explication de correction": "Explication de correction",
      points: "Points",
      position: "Position",
      notion: "Notion",
      "bonne réponse": "Bonne réponse",
    };
    const choice = /^proposition ([A-D])$/.exec(label);
    return t("Question {0}, {1} : {2}", [
      Number(question[1]),
      choice ? t("Proposition ") + choice[1] : t(labels[label] || label),
      t(question[3]),
    ]);
  }
  const separator = reason.indexOf(" : ");
  return separator < 0
    ? t(reason)
    : `${t(reason.slice(0, separator))} : ${t(reason.slice(separator + 3))}`;
}
export function LanguageNotice() {
  return (
    <p className="field-help quiz-language-notice">
      {t(
        "La langue choisie traduit l’interface du module Quiz et sa navigation. Les questions et le contenu pédagogique restent dans leur langue d’origine.",
      )}
    </p>
  );
}
