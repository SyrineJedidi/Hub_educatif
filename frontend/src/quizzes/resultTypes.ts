import { locale } from "./i18n";
import type { AttemptQuestion, AttemptSummary, Choice } from "./attemptTypes";
export interface Person {
  id: string;
  first_name: string;
  last_name: string;
}
export interface ManagedResult extends AttemptSummary {
  student: Person;
  learning_group: { id: string; name: string };
  teacher: Person;
  percentage: number | null;
}
export interface ManagedResultDetail extends ManagedResult {
  questions: (AttemptQuestion & {
    correct_answer: Choice;
    explanation: string;
    selected_choice: Choice | null;
    is_correct: boolean | null;
    points_earned: number | null;
  })[];
}
export const personName = (person: Person) =>
  `${person.last_name} ${person.first_name}`.trim();
export const percentageLabel = (value: number) =>
  new Intl.NumberFormat(locale(), { maximumFractionDigits: 2 }).format(value) +
  " %";
