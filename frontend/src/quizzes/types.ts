export type QuizStatus = "DRAFT" | "PUBLISHED" | "ARCHIVED";
export type Level = "EASY" | "MEDIUM" | "HARD";
export interface Quiz {
  id: string;
  title: string;
  description: string;
  learning_group_id: string;
  learning_group_name: string;
  level: Level;
  duration_minutes: number | null;
  max_attempts: number;
  status: QuizStatus;
  published_at: string | null;
  question_count: number;
  total_points: number;
  teacher_id?: string;
  teacher_name?: string;
  created_at?: string;
  updated_at?: string;
  next_position?: number;
}
export interface Question {
  id: string;
  quiz_id: string;
  statement: string;
  choice_a: string;
  choice_b: string;
  choice_c: string;
  choice_d: string;
  correct_answer: "A" | "B" | "C" | "D";
  explanation: string;
  points: number;
  position: number;
}
export interface Preview {
  quiz: Quiz;
  questions: Question[];
  publication_blockers: string[];
}
export const levels: Record<Level, string> = {
  EASY: "Facile",
  MEDIUM: "Intermédiaire",
  HARD: "Difficile",
};
export const quizStatuses: Record<QuizStatus, string> = {
  DRAFT: "Brouillon",
  PUBLISHED: "Publié",
  ARCHIVED: "Archivé",
};
export const quizVisibility: Record<QuizStatus, string> = {
  DRAFT:
    "Enseignant propriétaire et administrateur uniquement. Masqué aux étudiants.",
  PUBLISHED:
    "Accessible aux étudiants actuellement inscrits dans le groupe ciblé, à l’enseignant propriétaire et à l’administrateur.",
  ARCHIVED:
    "Conservé pour l’enseignant propriétaire et l’administrateur uniquement. Masqué aux étudiants.",
};
