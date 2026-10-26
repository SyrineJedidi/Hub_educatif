export type CourseStatus = "DRAFT" | "PUBLISHED" | "ARCHIVED";
export type ResourceKind = "PDF" | "AUDIO";
export type ProcessingStatus =
  | "PENDING"
  | "PROCESSING"
  | "READY"
  | "NO_TEXT"
  | "FAILED";
export type JobStatus = "PENDING" | "RUNNING" | "DONE" | "FAILED";
export type SearchType = "course" | "chapter" | "resource" | "segment";
export interface Person {
  id: string;
  first_name: string;
  last_name: string;
}
export interface SubjectSummary {
  id: string;
  name: string;
  code: string;
}
export interface Subject extends SubjectSummary {
  description: string;
  archived: boolean;
  created_by: Person;
  courses_count: number;
  can_edit: boolean;
  created_at: string;
  updated_at: string;
}
export interface CourseGroup {
  id: string;
  name: string;
  code: string;
  archived: boolean;
}
export interface ProcessingJob {
  status: JobStatus;
  status_label: string;
  attempts: number;
  provider: string;
  model_name: string;
  audio_seconds: number | null;
  processing_ms: number | null;
  segments_count: number | null;
  error: string;
  created_at: string;
  finished_at: string | null;
}
export interface Resource {
  id: string;
  course_id: string;
  chapter_id: string;
  kind: ResourceKind;
  kind_label: string;
  title: string;
  description: string;
  position: number;
  original_name: string;
  size: number;
  page_count: number | null;
  duration_seconds: number | null;
  language: string;
  processing_status: ProcessingStatus;
  processing_label: string;
  segments_count: number;
  file_url: string;
  download_url: string;
  mime_type?: string;
  processing_error?: string;
  text_version?: number;
  job?: ProcessingJob | null;
  created_at?: string;
  updated_at?: string;
  viewed?: boolean;
}
export interface ResourceDetail extends Resource {
  chapter?: { id: string; title: string };
  course?: { id: string; title: string };
}
export interface Chapter {
  id: string;
  course_id: string;
  title: string;
  description: string;
  position: number;
  resources: Resource[];
}
export interface Progress {
  viewed: number;
  total: number;
  percent: number;
}
export interface Course {
  id: string;
  title: string;
  description: string;
  subject: SubjectSummary;
  teacher: Person;
  chapters_count: number;
  resources_count: number;
  updated_at: string;
  status?: CourseStatus;
  status_label?: string;
  groups?: CourseGroup[];
  processing_count?: number;
  content_version?: number;
  published_at?: string | null;
  created_at?: string;
  can_delete?: boolean;
  progress?: Progress;
  chapters?: Chapter[];
  publication_blockers?: string[];
}
export interface Segment {
  id: string;
  order: number;
  text: string;
  page: number | null;
  start_seconds: number | null;
  end_seconds: number | null;
  edited: boolean;
  edited_at: string | null;
}
export interface Segments {
  count: number;
  results: Segment[];
}
export interface ViewResult {
  viewed: boolean;
  view_count: number;
  progress: Progress;
}
export interface ProcessingInfo {
  provider: string;
  configured: boolean;
  model: string;
  process_inline: boolean;
  pending: number;
  running: number;
  failed: number;
}
export interface SearchResult {
  type: SearchType;
  score: number;
  course: { id: string; title: string };
  chapter: { id: string; title: string } | null;
  resource: { id: string; title: string; kind: ResourceKind } | null;
  snippet: string;
  highlights: [number, number][];
  page: number | null;
  start_seconds: number | null;
  link: string;
}
export interface Statistics {
  course: { id: string; title: string };
  summary: {
    students: number;
    resources: number;
    average_percent: number | null;
    completed_students: number;
  };
  resources: {
    id: string;
    title: string;
    kind: ResourceKind;
    chapter_title: string;
    viewers: number;
    rate: number | null;
    total_views: number;
  }[];
  students: (Person & {
    viewed: number;
    total: number;
    percent: number | null;
    last_viewed_at: string | null;
  })[];
}
export const courseStatuses: Record<CourseStatus, string> = {
  DRAFT: "Brouillon",
  PUBLISHED: "Publié",
  ARCHIVED: "Archivé",
};
export const courseVisibility: Record<CourseStatus, string> = {
  DRAFT:
    "Enseignant propriétaire et administrateur uniquement. Masqué aux étudiants.",
  PUBLISHED:
    "Accessible aux étudiants actuellement inscrits dans les groupes associés, à l’enseignant propriétaire et à l’administrateur.",
  ARCHIVED:
    "En lecture seule pour l’enseignant propriétaire et l’administrateur. Masqué aux étudiants.",
};
export const resourceKinds: Record<ResourceKind, string> = {
  PDF: "Document PDF",
  AUDIO: "Enregistrement audio",
};
export const kindIcons: Record<ResourceKind, string> = {
  PDF: "ti-file",
  AUDIO: "ti-headphone-alt",
};
export const processingStatuses: Record<ProcessingStatus, string> = {
  PENDING: "En attente",
  PROCESSING: "En cours de traitement",
  READY: "Prêt",
  NO_TEXT: "Sans texte exploitable",
  FAILED: "Échec du traitement",
};
export const searchTypes: Record<SearchType, string> = {
  course: "Cours",
  chapter: "Chapitre",
  resource: "Ressource",
  segment: "Extrait",
};
export const isProcessing = (resource: Resource) =>
  resource.processing_status === "PENDING" ||
  resource.processing_status === "PROCESSING";
