export type Priority = "LOW" | "MEDIUM" | "HIGH";
export type GoalStatus = "ACTIVE" | "ACHIEVED" | "ABANDONED";
export type DeadlineKind = "EXAM" | "QUIZ" | "ASSIGNMENT" | "OTHER";
export type PlanStatus = "DRAFT" | "ACTIVE" | "ARCHIVED";
export type Generator = "AI" | "RULES";
export type TaskStatus = "TODO" | "DONE" | "SKIPPED";
export type TaskSource = "AI" | "RULES" | "MANUAL";
export type GenerationMode = "ai" | "rules";
export interface Reference {
  id: string;
  title: string;
}
export interface GroupReference {
  id: string;
  name: string;
  code: string;
}
export interface Person {
  id: string;
  first_name: string;
  last_name: string;
}
export interface Goal {
  id: string;
  title: string;
  description: string;
  learning_group: GroupReference | null;
  target_date: string | null;
  priority: Priority;
  priority_label: string;
  estimated_hours: number;
  status: GoalStatus;
  status_label: string;
  planned_minutes: number;
  done_minutes: number;
  created_at: string;
  updated_at: string;
}
export interface Deadline {
  id: string;
  title: string;
  kind: DeadlineKind;
  kind_label: string;
  due_at: string;
  goal: Reference | null;
  notes: string;
  created_at: string;
  updated_at: string;
}
export interface Slot {
  id: string;
  weekday: number;
  weekday_label: string;
  start_time: string;
  end_time: string;
  minutes: number;
}
export interface Availability {
  results: Slot[];
  weekly_minutes: number;
}
export interface Task {
  id: string;
  plan_id: string;
  title: string;
  description: string;
  goal: Reference | null;
  deadline: Reference | null;
  starts_at: string;
  ends_at: string;
  minutes: number;
  status: TaskStatus;
  status_label: string;
  source: TaskSource;
  completed_at: string | null;
}
export interface Plan {
  id: string;
  title: string;
  start_date: string;
  end_date: string;
  status: PlanStatus;
  status_label: string;
  generator: Generator;
  generator_label: string;
  fallback_reason: string;
  provider: string;
  model_name: string;
  latency_ms: number | null;
  prompt_tokens: number | null;
  output_tokens: number | null;
  tasks_count: number;
  done_count: number;
  planned_minutes: number;
  activated_at: string | null;
  created_at: string;
  updated_at: string;
}
export interface PlanDetail extends Plan {
  advice: string;
  tasks: Task[];
}
export interface Progress {
  done: number;
  skipped: number;
  todo: number;
  overdue: number;
  planned_minutes: number;
  done_minutes: number;
  completion_rate: number | null;
}
export interface GoalMinutes {
  id: string;
  title: string;
  planned_minutes: number;
  done_minutes: number;
}
export interface Dashboard {
  active_plan: Plan | null;
  today: Task[];
  upcoming: Task[];
  progress: Progress;
  streak_days: number;
  next_deadlines: Deadline[];
  goals: GoalMinutes[];
}
export interface QuizResult {
  quiz_title: string;
  group_name: string;
  percent: number | null;
  submitted_at: string;
}
export interface PlannerContext {
  goals: number;
  deadlines: number;
  weekly_minutes: number;
  quiz_results: QuizResult[];
  weak_groups: string[];
  courses_available: boolean;
  courses: { title: string; chapters: number }[];
  ai: {
    provider: string;
    configured: boolean;
    model: string | null;
    remaining_today: number;
  };
}
export interface CoachStudent {
  student: Person;
  groups: { id: string; name: string }[];
  active_plan: {
    id: string;
    title: string;
    start_date: string;
    end_date: string;
  } | null;
  progress: Progress;
  last_done_at: string | null;
  next_deadline: { title: string; due_at: string } | null;
}
export interface CoachGoal extends GoalMinutes {
  priority: Priority;
  priority_label: string;
  status: GoalStatus;
  status_label: string;
}
export interface CoachStudentDetail {
  student: Person;
  groups: { id: string; name: string }[];
  progress: Progress;
  streak_days: number;
  goals: CoachGoal[];
  deadlines: {
    id: string;
    title: string;
    kind_label: string;
    due_at: string;
  }[];
  active_plan: (Plan & { advice?: string; tasks: Task[] }) | null;
}
export const priorities: Record<Priority, string> = {
  LOW: "Faible",
  MEDIUM: "Moyenne",
  HIGH: "Haute",
};
export const goalStatuses: Record<GoalStatus, string> = {
  ACTIVE: "En cours",
  ACHIEVED: "Atteint",
  ABANDONED: "Abandonné",
};
export const deadlineKinds: Record<DeadlineKind, string> = {
  EXAM: "Examen",
  QUIZ: "Quiz",
  ASSIGNMENT: "Devoir",
  OTHER: "Autre",
};
export const planStatuses: Record<PlanStatus, string> = {
  DRAFT: "Brouillon",
  ACTIVE: "Actif",
  ARCHIVED: "Archivé",
};
export const generators: Record<Generator, string> = {
  AI: "IA (Gemini)",
  RULES: "Règles",
};
export const taskStatuses: Record<TaskStatus, string> = {
  TODO: "À faire",
  DONE: "Terminée",
  SKIPPED: "Ignorée",
};
export const taskSources: Record<TaskSource, string> = {
  AI: "Proposée par l’IA",
  RULES: "Calculée par règles",
  MANUAL: "Ajoutée à la main",
};
export const weekdays = [
  "Lundi",
  "Mardi",
  "Mercredi",
  "Jeudi",
  "Vendredi",
  "Samedi",
  "Dimanche",
];
