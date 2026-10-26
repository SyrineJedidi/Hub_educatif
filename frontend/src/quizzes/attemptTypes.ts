export type Choice = "A" | "B" | "C" | "D";
export interface AttemptQuestion {
  id: string;
  statement: string;
  choice_a: string;
  choice_b: string;
  choice_c: string;
  choice_d: string;
  points: number;
  position: number;
}
export interface SavedAnswer {
  question_id: string;
  selected_choice: Choice;
  revision: number;
}
export interface AttemptSummary {
  id: string;
  quiz_id: string;
  quiz_title: string;
  number: number;
  status: "IN_PROGRESS" | "SUBMITTED" | "EXPIRED";
  started_at: string;
  deadline: string | null;
  ended_at: string | null;
  points_earned: number | null;
  total_points: number;
  server_time: string;
}
export interface Attempt extends AttemptSummary {
  questions: AttemptQuestion[];
  answers: SavedAnswer[];
}
export interface AttemptResult extends AttemptSummary {
  percentage: number;
  questions: (AttemptQuestion & {
    correct_answer: Choice;
    explanation: string;
    selected_choice: Choice | null;
    is_correct: boolean;
    points_earned: number;
  })[];
}
export interface QuizAttempts {
  quiz_status: string;
  attempts_used: number;
  max_attempts: number;
  remaining_attempts: number;
  current_attempt_id: string | null;
  attempts: AttemptSummary[];
}
export const attemptLabels = {
  IN_PROGRESS: "En cours",
  SUBMITTED: "Soumise",
  EXPIRED: "Expirée",
};
export const attemptPath = (attempt: AttemptSummary) =>
  `/espace/tentatives/${attempt.id}${attempt.status === "IN_PROGRESS" ? "" : "/resultat"}`;
