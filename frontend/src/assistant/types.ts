export type SourceType = "course" | "group";
export type Mode = "EXPLICATION" | "INDICE";
export type ConversationStatus = "ACTIVE" | "ARCHIVED" | "DELETED";
export type MessageStatus = "COMPLETE" | "OUT_OF_SCOPE" | "FAILED" | "BLOCKED";
export type InputMode = "TEXT" | "VOICE";
export type Rating = "UP" | "DOWN";
export type Reason =
  | "INCORRECT"
  | "HORS_SUJET"
  | "INCOMPLETE"
  | "UNCLEAR"
  | "BAD_SOURCE"
  | "OTHER";
export type FeedbackStatus = "NEW" | "CONFIRMED" | "CORRECTED" | "DISMISSED";
export type SourceKind = "RESOURCE" | "NOTE" | "VALIDATED";
export interface Person {
  id: string;
  first_name: string;
  last_name: string;
}
export interface Quota {
  limit: number;
  used: number;
  remaining: number;
}
export interface Scope {
  source_type: SourceType;
  scope_id: string;
  key: string;
  title: string;
  teacher: Person | null;
  enabled: boolean;
  default_mode: Mode;
  allow_mode_choice: boolean;
  suggested_questions: string[];
  welcome_message: string;
  quota?: Quota;
}
// `available` is false when the server has no transcription service.
export interface VoiceSettings {
  available: boolean;
  max_seconds: number;
  max_mb: number;
}
export interface ScopeList {
  results: Scope[];
  voice?: VoiceSettings;
}
export interface ManagedScope extends Scope {
  daily_question_limit: number;
  effective_daily_limit?: number;
  max_daily_question_limit?: number;
  block_during_quiz: boolean;
  updated_at?: string | null;
}
export interface Conversation {
  id: string;
  source_type: SourceType;
  scope_id: string;
  scope_key: string;
  scope_title: string;
  title: string;
  mode: Mode;
  mode_label: string;
  status: ConversationStatus;
  status_label: string;
  pinned: boolean;
  message_count: number;
  last_message_at: string | null;
  created_at: string;
  purge_at: string | null;
  can_send: boolean;
}
export interface Citation {
  number: number;
  source_kind: SourceKind;
  source_id: string;
  source_title: string;
  chapter_title: string;
  page: number | null;
  start_seconds: number | null;
  url: string;
  excerpt: string;
  score: number;
}
export interface Feedback {
  rating: Rating;
  reasons: Reason[];
  comment: string;
  shared_with_teacher: boolean;
  status: FeedbackStatus;
  status_label: string;
  teacher_note: string;
}
export interface Message {
  id: string;
  conversation_id: string;
  role: "USER" | "ASSISTANT";
  reply_to_id?: string | null;
  content: string;
  input_mode: InputMode;
  status: MessageStatus;
  status_label: string;
  unsourced: boolean;
  citations: Citation[];
  follow_ups: string[];
  latency_ms?: number | null;
  created_at: string;
  feedback?: Feedback | null;
}
export interface MessagePage {
  results: Message[];
  has_more: boolean;
}
export interface SendResult {
  question: Message;
  answer: Message;
  conversation: Conversation;
  quota: Quota;
}
export interface Transcription {
  text: string;
  language: string;
  duration_seconds: number | null;
}
export interface FeedbackInput {
  rating: Rating;
  reasons: Reason[];
  comment: string;
  shared_with_teacher: boolean;
}
export interface Note {
  id: string;
  group: { id: string; name: string; code: string };
  title: string;
  body: string;
  version: number;
  teacher: Person | null;
  created_at: string;
  updated_at: string;
}
export interface SettingsInput {
  enabled: boolean;
  default_mode: Mode;
  allow_mode_choice: boolean;
  daily_question_limit: number;
  block_during_quiz: boolean;
  suggested_questions: string[];
  welcome_message: string;
}
export interface Review {
  id: string;
  scope_key: string;
  scope_title: string;
  question: string;
  answer: { content: string; citations: Citation[]; created_at: string };
  rating: Rating;
  reasons: Reason[];
  reason_labels?: string[];
  comment: string;
  status: FeedbackStatus;
  status_label: string;
  teacher_note: string;
  reviewed_at: string | null;
  created_at: string;
}
export type ReviewAction = "CONFIRM" | "CORRECT" | "DISMISS";
// Ratios are fractions between 0 and 1; null when nothing can be computed.
export interface Insights {
  period?: { from: string; to: string };
  questions?: number;
  active_students?: number;
  voice_questions?: number;
  voice_share?: number | null;
  answers_by_status?: Partial<Record<MessageStatus, number>>;
  satisfaction?: number | null;
  feedback?: { up: number; down: number; shared: number };
  out_of_scope_rate?: number | null;
  latency_ms?: { p50: number | null; p95: number | null };
  questions_per_day?: { date: string; questions: number }[];
  top_sources?: {
    source_kind: SourceKind;
    source_id: string;
    title: string;
    count: number;
  }[];
  unanswered_questions?: { question: string; count: number }[];
  low_rated_answers?: number;
}
export interface UsageDay {
  date: string;
  questions: number;
  gemini_calls: number;
  failures: number;
  prompt_tokens: number;
  output_tokens: number;
}
export interface ProviderStatus {
  provider: string;
  configured: boolean;
  model: string;
  fallback_model?: string;
}
export interface Usage {
  period?: { from: string; to: string };
  days?: UsageDay[];
  totals?: Omit<UsageDay, "date">;
  failures_by_code?: Record<string, number>;
  top_scopes?: {
    scope_key: string;
    source_type: SourceType;
    scope_id: string;
    title: string;
    questions: number;
  }[];
  providers?: { llm?: ProviderStatus; transcription?: ProviderStatus };
  limits?: {
    global_daily_budget?: Quota;
    daily_questions_per_user?: number;
    voice_per_hour?: number;
    max_audio_seconds?: number;
  };
}

export const modes: Record<Mode, string> = {
  EXPLICATION: "Explication",
  INDICE: "Indice",
};
export const modeHelp: Record<Mode, string> = {
  EXPLICATION: "Une explication complète, avec un exemple si utile.",
  INDICE:
    "Des pistes et des questions pour trouver la réponse par vous-même, sans la solution finale.",
};
export const sourceTypes: Record<SourceType, string> = {
  course: "Cours",
  group: "Notes du groupe",
};
export const messageStatuses: Record<MessageStatus, string> = {
  COMPLETE: "Réponse",
  OUT_OF_SCOPE: "Hors cours",
  FAILED: "Échec",
  BLOCKED: "Bloquée",
};
export const conversationStatuses: Record<ConversationStatus, string> = {
  ACTIVE: "Active",
  ARCHIVED: "Archivée",
  DELETED: "Corbeille",
};
export const ratings: Record<Rating, string> = {
  UP: "Utile",
  DOWN: "À améliorer",
};
export const reasons: Record<Reason, string> = {
  INCORRECT: "Incorrecte",
  HORS_SUJET: "Hors sujet",
  INCOMPLETE: "Incomplète",
  UNCLEAR: "Pas claire",
  BAD_SOURCE: "Source erronée",
  OTHER: "Autre",
};
export const feedbackStatuses: Record<FeedbackStatus, string> = {
  NEW: "Nouveau",
  CONFIRMED: "Réponse confirmée",
  CORRECTED: "Correction publiée",
  DISMISSED: "Classé sans suite",
};
export const sourceKinds: Record<SourceKind, string> = {
  RESOURCE: "Ressource du cours",
  NOTE: "Note de l’enseignant",
  VALIDATED: "Réponse validée par l’enseignant",
};
export const llmProviders: Record<string, string> = {
  disabled: "Désactivé",
  fake: "Simulé (tests)",
  gemini: "Google Gemini",
};
export const errorCodes: Record<string, string> = {
  disabled: "Assistant non configuré",
  unknown: "Cause inconnue",
  quota: "Quota du fournisseur atteint",
  unavailable: "Service indisponible",
  auth: "Clé d’accès refusée",
  blocked: "Réponse bloquée",
  invalid_response: "Réponse illisible",
  refused: "Requête refusée",
};
export const QUESTION_MAX = 2000;
export const FEEDBACK_COMMENT_MAX = 500;
