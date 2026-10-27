export type SheetStatus = "DRAFT" | "PUBLISHED" | "ARCHIVED";
export type SheetColor = "INDIGO" | "CORAL" | "TEAL" | "AMBER" | "ROSE" | "SKY";
export interface GlossaryEntry {
  term: string;
  definition: string;
}
export interface Illustration {
  id: string;
  sheet_id: string;
  url: string;
  caption: string;
  prompt: string;
  source: "UPLOAD" | "AI";
  ai_model: string;
  width: number;
  height: number;
  position: number;
  created_at: string;
}
export interface SheetSummary {
  id: string;
  title: string;
  course_label: string;
  excerpt: string;
  tags: string[];
  color: SheetColor;
  status: SheetStatus;
  pinned: boolean;
  personal: boolean;
  ai_generated: boolean;
  ai_reviewed: boolean;
  owner_id: string;
  owner_name: string;
  learning_group_id: string | null;
  learning_group_name: string | null;
  key_point_count: number;
  illustration_count: number;
  cover_url: string | null;
  can_edit: boolean;
  created_at: string;
  updated_at: string;
  published_at: string | null;
}
export interface Sheet extends SheetSummary {
  summary: string;
  key_points: string[];
  glossary: GlossaryEntry[];
  ai_model: string;
  generated_at: string | null;
  source_name: string;
  illustration_prompt: string;
  illustrations: Illustration[];
  publication_blockers: string[];
  generation?: {
    model: string;
    duration_ms: number;
    source_characters: number;
    fallback: boolean;
  };
}
export interface Facets {
  courses: string[];
  tags: { name: string; count: number }[];
  stats: Record<
    "total" | "published" | "draft" | "archived" | "pinned" | "ai",
    number
  >;
}
export const sheetStatuses: Record<SheetStatus, string> = {
  DRAFT: "Brouillon",
  PUBLISHED: "Publiée",
  ARCHIVED: "Archivée",
};
export const sheetColors: Record<SheetColor, string> = {
  INDIGO: "Indigo",
  CORAL: "Corail",
  TEAL: "Émeraude",
  AMBER: "Ambre",
  ROSE: "Rose",
  SKY: "Ciel",
};
export const summaryLengths = {
  SHORT: ["Synthétique", "150 à 250 mots, l’essentiel en un coup d’œil."],
  STANDARD: ["Standard", "350 à 550 mots, structurée par parties."],
  DETAILED: ["Approfondie", "700 à 1000 mots, pour réviser en détail."],
} as const;
export const illustrationStyles = {
  SCHEMA: ["Schéma pédagogique", "ti-layout-grid3"],
  FLAT: ["Flat design", "ti-palette"],
  REALISTIC: ["Réaliste", "ti-camera"],
  WATERCOLOR: ["Aquarelle", "ti-brush-alt"],
} as const;
export function statusLabel(sheet: SheetSummary) {
  return sheet.personal ? "Personnelle" : sheetStatuses[sheet.status];
}
export type JobStatus = "QUEUED" | "RUNNING" | "SUCCEEDED" | "FAILED";
export interface QualityMetrics {
  source_words: number;
  summary_words: number;
  compression: number | null;
  keyword_coverage: number | null;
  keywords_missing: string[];
  key_points: number;
  glossary_terms: number;
  checks: Record<string, boolean>;
  structure_score: number;
}
export interface AIJob {
  id: string;
  kind: "SUMMARY" | "ILLUSTRATION" | "QUIZ";
  status: JobStatus;
  sheet_id: string | null;
  sheet_title: string;
  engine: string;
  model: string;
  fallback: boolean;
  error: string;
  params: {
    length?: keyof typeof summaryLengths;
    style?: keyof typeof illustrationStyles;
    caption?: string;
    prompt?: string;
    source_characters?: number;
    count?: number;
  };
  source_name: string;
  metrics: Partial<QualityMetrics>;
  rating: number | null;
  duration_ms: number | null;
  queue_ms: number | null;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
  illustration: Illustration | null;
  user_name?: string;
  result?: { questions?: SelfQuizQuestion[] };
}
/** Question of the training quiz written by the AI from a sheet. */
export interface SelfQuizQuestion {
  question: string;
  choices: string[];
  answer: number;
  explanation: string;
}
export interface AIStatus {
  summary: boolean;
  illustration: boolean;
  summary_engine: string | null;
  fallback_engine: string | null;
  illustration_engine: string | null;
  asynchronous: boolean;
  job_backend: string;
}
export interface AIMetrics {
  period_days: number;
  totals: Record<
    "jobs" | "summaries" | "illustrations" | "running" | "succeeded" | "failed",
    number
  >;
  success_rate: number | null;
  fallback_rate: number | null;
  latency: {
    engine: string;
    count: number;
    mean_ms: number;
    p50_ms: number;
    p95_ms: number;
  }[];
  queue_mean_ms: number | null;
  quality: Record<
    "keyword_coverage" | "compression" | "structure_score",
    number | null
  >;
  rating: { mean: number | null; count: number; distribution: number[] };
  review_rate: number | null;
  per_day: { date: string; count: number }[];
  errors: [string, number][];
  recent: AIJob[];
  configuration: {
    job_backend: string;
    gemini_model: string | null;
    ollama_model: string | null;
    image_model: string | null;
  };
}
export const jobStatuses: Record<JobStatus, [string, string]> = {
  QUEUED: ["En attente", "ti-time"],
  RUNNING: ["En cours", "ti-reload"],
  SUCCEEDED: ["Terminée", "ti-check"],
  FAILED: ["Échec", "ti-alert"],
};
export const engines: Record<string, string> = {
  gemini: "Gemini",
  ollama: "Ollama (local)",
  huggingface: "Hugging Face",
};
export const seconds = (ms: number | null | undefined) =>
  ms == null
    ? "—"
    : (ms / 1000).toLocaleString("fr-FR", { maximumFractionDigits: 1 }) + " s";
export const percent = (value: number | null | undefined) =>
  value == null ? "—" : Math.round(value * 100) + " %";
