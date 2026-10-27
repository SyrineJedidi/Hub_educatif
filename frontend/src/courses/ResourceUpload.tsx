import { useId, useRef, useState } from "react";
import type { FormEvent } from "react";
import { api } from "../api/client";
import { Alert, Field, Textarea } from "../components/UI";
import { useFormValidation } from "../quizzes/useFormValidation";
import type { Chapter, Resource } from "./types";
import { titleFromFile } from "./format";
import {
  DESCRIPTION_MAX_LENGTH,
  MAX_AUDIO_MB,
  MAX_PDF_MB,
  TITLE_MAX_LENGTH,
  validateUpload,
} from "./validation";
function uploadMessage(resource: Resource) {
  const name = `« ${resource.title} » a été importé.`;
  switch (resource.processing_status) {
    case "READY":
      return `${name} Son texte est prêt pour la consultation et la recherche.`;
    case "PENDING":
    case "PROCESSING":
      return resource.kind === "AUDIO"
        ? `${name} La transcription est en attente de traitement.`
        : `${name} L’extraction du texte est en cours.`;
    case "NO_TEXT":
      return `${name} ${resource.processing_error || "Aucun texte exploitable n’a été trouvé."}`;
    default:
      return `${name} Le traitement a échoué : ${resource.processing_error || "réessayez plus tard."}`;
  }
}
export default function ResourceUpload({
  courseId,
  chapter,
  number,
  onUploaded,
}: {
  courseId: string;
  chapter: Chapter;
  number: number;
  onUploaded: () => void;
}) {
  const [open, setOpen] = useState(!chapter.resources.length),
    [file, setFile] = useState<File | null>(null),
    [fileKey, setFileKey] = useState(0),
    [title, setTitle] = useState(""),
    [titleEdited, setTitleEdited] = useState(false),
    [description, setDescription] = useState(""),
    [busy, setBusy] = useState(false),
    [error, setError] = useState<unknown>(),
    [status, setStatus] = useState("");
  const locked = useRef(false),
    help = useId();
  const validation = useFormValidation(
    () => validateUpload({ file, title, description }),
    {
      file: file ? [file.name, file.size, file.lastModified].join("/") : "",
      title,
      description,
    },
  );
  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (locked.current) return;
    setError(undefined);
    setStatus("");
    try {
      validation.check();
    } catch (issue) {
      setError(issue);
      return;
    }
    locked.current = true;
    setBusy(true);
    const body = new FormData();
    body.append("chapter_id", chapter.id);
    body.append("title", title.trim());
    body.append("description", description.trim());
    body.append("file", file!);
    try {
      const resource = await api<Resource>(
        "courses/" + courseId + "/resources/",
        "POST",
        body,
      );
      setStatus(uploadMessage(resource));
      setFile(null);
      setFileKey((key) => key + 1);
      setTitle("");
      setTitleEdited(false);
      setDescription("");
      onUploaded();
    } catch (issue) {
      validation.serverErrors(issue);
      setError(issue);
    } finally {
      locked.current = false;
      setBusy(false);
    }
  }
  return (
    <details
      className="course-upload"
      open={open}
      onToggle={(e) => setOpen(e.currentTarget.open)}
    >
      <summary>
        Importer une ressource
        <span className="visually-hidden"> dans le chapitre {number}</span> +
      </summary>
      <form
        noValidate
        onSubmit={submit}
        ref={validation.formProps.formRef}
        onBlur={validation.formProps.onBlur}
        onChange={() => setError(undefined)}
      >
        <Alert error={error} />
        <Field
          key={fileKey}
          label="Fichier PDF ou audio"
          name="file"
          type="file"
          accept=".pdf,application/pdf,audio/*"
          required
          aria-describedby={help}
          error={validation.errors.file}
          onChange={(e) => {
            const next = e.target.files?.[0] || null;
            setFile(next);
            setStatus("");
            if (next && !titleEdited) setTitle(titleFromFile(next.name));
          }}
        />
        <p id={help} className="field-help">
          PDF jusqu’à {MAX_PDF_MB} Mo, ou audio MP3, M4A, WAV, OGG, WEBM ou FLAC
          jusqu’à {MAX_AUDIO_MB} Mo. Le texte des PDF est extrait
          automatiquement et les enregistrements audio sont transcrits.
        </p>
        <Field
          label="Titre de la ressource"
          name="title"
          value={title}
          required
          maxLength={TITLE_MAX_LENGTH}
          error={validation.errors.title}
          onChange={(e) => {
            setTitle(e.target.value);
            setTitleEdited(e.target.value.trim() !== "");
          }}
        />
        <Textarea
          label="Description (facultative)"
          name="description"
          rows={2}
          value={description}
          maxLength={DESCRIPTION_MAX_LENGTH}
          error={validation.errors.description}
          onChange={(e) => setDescription(e.target.value)}
        />
        <button className="btn_one" aria-disabled={busy || undefined}>
          Importer la ressource
          <span className="visually-hidden"> dans le chapitre {number}</span>
        </button>
        <div className="course-upload-status" role="status" aria-live="polite">
          {busy && (
            <>
              <progress aria-label="Import en cours" />
              <p>Import en cours…</p>
            </>
          )}
          {!busy && status && <p>{status}</p>}
        </div>
      </form>
    </details>
  );
}
