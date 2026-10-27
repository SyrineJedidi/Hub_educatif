export type FieldErrors = Record<string, string>;
export const TITLE_MAX_LENGTH = 120;
export const COURSE_DESCRIPTION_MAX_LENGTH = 2000;
export const DESCRIPTION_MAX_LENGTH = 1000;
export const SUBJECT_NAME_MAX_LENGTH = 80;
export const SEGMENT_MAX_LENGTH = 20000;
export const MAX_GROUPS = 20;
export const MAX_PDF_MB = 20;
export const MAX_AUDIO_MB = 25;
const SUBJECT_CODE = /^[A-Z0-9][A-Z0-9-]{1,19}$/u;
const AUDIO_EXTENSIONS = [
  "mp3",
  "m4a",
  "mp4",
  "wav",
  "ogg",
  "oga",
  "opus",
  "webm",
  "flac",
];

function textError(value: string, label: string, max: number, required = true) {
  if (required && !value.trim()) return `${label} est obligatoire.`;
  if (Array.from(value.trim()).length > max)
    return `${label} doit contenir au maximum ${max} caractères.`;
  return "";
}

function nonEmptyErrors(errors: FieldErrors): FieldErrors {
  return Object.fromEntries(
    Object.entries(errors).filter(([, value]) => value),
  );
}

export function validateCourse(
  values: {
    title: string;
    description: string;
    subject: string;
    groups: string[];
    teacher: string;
  },
  allowed: { subjects: string[]; groups: string[]; teachers?: string[] },
): FieldErrors {
  const errors: FieldErrors = {
    title: textError(values.title, "Le titre", TITLE_MAX_LENGTH),
    description: textError(
      values.description,
      "La description",
      COURSE_DESCRIPTION_MAX_LENGTH,
    ),
    subject_id: allowed.subjects.includes(values.subject)
      ? ""
      : "Sélectionnez une matière active.",
    group_ids: !values.groups.length
      ? "Sélectionnez au moins un groupe actif."
      : values.groups.length > MAX_GROUPS
        ? `Sélectionnez au maximum ${MAX_GROUPS} groupes.`
        : values.groups.every((id) => allowed.groups.includes(id))
          ? ""
          : "Sélectionnez uniquement des groupes actifs affectés à l’enseignant.",
  };
  if (allowed.teachers)
    errors.teacher_id = allowed.teachers.includes(values.teacher)
      ? ""
      : "Sélectionnez un enseignant actif.";
  return nonEmptyErrors(errors);
}

export function validateChapter(values: {
  title: string;
  description: string;
}): FieldErrors {
  return nonEmptyErrors({
    title: textError(values.title, "Le titre", TITLE_MAX_LENGTH),
    description: textError(
      values.description,
      "La description",
      DESCRIPTION_MAX_LENGTH,
      false,
    ),
  });
}

export function validateResource(
  values: { title: string; description: string; chapter: string },
  chapters: string[],
): FieldErrors {
  return nonEmptyErrors({
    title: textError(values.title, "Le titre", TITLE_MAX_LENGTH),
    description: textError(
      values.description,
      "La description",
      DESCRIPTION_MAX_LENGTH,
      false,
    ),
    chapter_id: chapters.includes(values.chapter)
      ? ""
      : "Sélectionnez un chapitre du cours.",
  });
}

export function validateSubject(values: {
  name: string;
  code: string;
  description: string;
}): FieldErrors {
  const code = values.code.trim().toUpperCase();
  return nonEmptyErrors({
    name: textError(values.name, "Le nom", SUBJECT_NAME_MAX_LENGTH),
    code: !code
      ? "Le code est obligatoire."
      : SUBJECT_CODE.test(code)
        ? ""
        : "Le code contient de 2 à 20 caractères : lettres, chiffres et tirets, sans tiret au début.",
    description: textError(
      values.description,
      "La description",
      DESCRIPTION_MAX_LENGTH,
      false,
    ),
  });
}

export function uploadKind(file: File): "PDF" | "AUDIO" | null {
  const extension = file.name.split(".").pop()?.toLowerCase() || "";
  if (file.type === "application/pdf" || extension === "pdf") return "PDF";
  if (file.type.startsWith("audio/") || AUDIO_EXTENSIONS.includes(extension))
    return "AUDIO";
  return null;
}

function fileError(file: File | null) {
  if (!file) return "Choisissez un fichier PDF ou audio.";
  const kind = uploadKind(file);
  if (!kind)
    return "Format non pris en charge : importez un PDF ou un fichier audio (MP3, M4A, WAV, OGG, WEBM, FLAC).";
  if (!file.size) return "Ce fichier est vide.";
  const max = kind === "PDF" ? MAX_PDF_MB : MAX_AUDIO_MB;
  if (file.size > max * 1024 * 1024)
    return kind === "PDF"
      ? `Ce PDF dépasse la taille maximale de ${max} Mo.`
      : `Cet enregistrement dépasse la taille maximale de ${max} Mo.`;
  return "";
}

export function validateUpload(values: {
  file: File | null;
  title: string;
  description: string;
}): FieldErrors {
  return nonEmptyErrors({
    file: fileError(values.file),
    title: textError(values.title, "Le titre", TITLE_MAX_LENGTH),
    description: textError(
      values.description,
      "La description",
      DESCRIPTION_MAX_LENGTH,
      false,
    ),
  });
}

export function validateSegment(text: string): FieldErrors {
  return nonEmptyErrors({
    text: textError(text, "Le texte", SEGMENT_MAX_LENGTH),
  });
}
