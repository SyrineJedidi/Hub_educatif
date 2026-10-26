import { useCallback, useEffect, useRef, useState } from "react";
import type { FormEvent } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { api, date } from "../api/client";
import { useResource } from "../hooks/useResource";
import { Alert, Badge, Loading, Textarea } from "../components/UI";
import { useFormValidation } from "../quizzes/useFormValidation";
import type {
  Course,
  Resource,
  ResourceDetail,
  Segment,
  Segments,
  ViewResult,
} from "./types";
import { isProcessing } from "./types";
import { clock, fileSize, plural, seconds, spokenDuration } from "./format";
import { useCourseContext } from "./useCourseContext";
import { CourseUnavailable } from "./CourseRoutes";
import { SEGMENT_MAX_LENGTH, validateSegment } from "./validation";
import "./courses.css";
export default function ResourceViewer() {
  const { student } = useCourseContext();
  return student ? <StudentViewer /> : <ManagerViewer />;
}
function StudentViewer() {
  const { id, resourceId } = useParams();
  const { data, error, loading, reload } = useResource<ResourceDetail>(
    "student/courses/" + id + "/resources/" + resourceId + "/",
  );
  if (loading) return <Loading />;
  if (!data)
    return (
      <CourseUnavailable
        title="Ressource indisponible"
        error={error}
        onRetry={reload}
      />
    );
  return (
    <ResourceView
      key={data.id}
      initial={data}
      courseId={id!}
      courseTitle={data.course?.title || ""}
      chapterTitle={data.chapter?.title || ""}
      editable={false}
    />
  );
}
function ManagerViewer() {
  const { id, resourceId } = useParams();
  const resource = useResource<Resource>(
    "courses/" + id + "/resources/" + resourceId + "/",
  );
  const course = useResource<Course>("courses/" + id + "/");
  if (resource.loading || course.loading) return <Loading />;
  if (!resource.data || !course.data)
    return (
      <CourseUnavailable
        title="Ressource indisponible"
        error={resource.error || course.error}
        onRetry={() => {
          resource.reload();
          course.reload();
        }}
      />
    );
  const chapter = course.data.chapters?.find(
    (c) => c.id === resource.data!.chapter_id,
  );
  return (
    <ResourceView
      key={resource.data.id}
      initial={resource.data}
      courseId={course.data.id}
      courseTitle={course.data.title}
      chapterTitle={chapter?.title || ""}
      editable={course.data.status !== "ARCHIVED"}
    />
  );
}
function wholeNumber(value: string | null, min: number) {
  if (!value || !/^[0-9]+$/u.test(value)) return null;
  const number = Number(value);
  return number >= min ? number : null;
}
function ResourceView({
  initial,
  courseId,
  courseTitle,
  chapterTitle,
  editable,
}: {
  initial: ResourceDetail;
  courseId: string;
  courseTitle: string;
  chapterTitle: string;
  editable: boolean;
}) {
  const { base, apiBase, student } = useCourseContext();
  const [params] = useSearchParams();
  const page = wholeNumber(params.get("page"), 1),
    start = wholeNumber(params.get("t"), 0);
  const path = apiBase + courseId + "/resources/" + initial.id + "/";
  const [resource, setResource] = useState<ResourceDetail>(initial),
    [segments, setSegments] = useState<Segment[] | null>(null),
    [segmentsError, setSegmentsError] = useState<unknown>(),
    [error, setError] = useState<unknown>(),
    [message, setMessage] = useState(""),
    [editing, setEditing] = useState<string | null>(null),
    [current, setCurrent] = useState(-1),
    [busy, setBusy] = useState(false);
  const mounted = useRef(true),
    refreshing = useRef(false),
    locked = useRef(false),
    status = useRef(initial.processing_status),
    tracked = useRef(""),
    applied = useRef<number | null>(null),
    focusAfterEdit = useRef<string | null>(null),
    audio = useRef<HTMLAudioElement>(null);
  const loadSegments = useCallback(async () => {
    try {
      const data = await api<Segments>(path + "segments/");
      if (!mounted.current) return;
      setSegments(data.results);
      setSegmentsError(undefined);
    } catch (e) {
      if (mounted.current) setSegmentsError(e);
    }
  }, [path]);
  useEffect(() => {
    mounted.current = true;
    void loadSegments();
    return () => {
      mounted.current = false;
    };
  }, [loadSegments]);
  // StrictMode replays effects; the ref keeps one consultation per opened resource.
  useEffect(() => {
    if (!student || tracked.current === initial.id) return;
    tracked.current = initial.id;
    api<ViewResult>(path + "views/", "POST", {})
      .then((result) => {
        if (mounted.current)
          setResource((value) => ({ ...value, viewed: result.viewed }));
      })
      .catch(() => undefined);
  }, [student, initial.id, path]);
  const refresh = useCallback(async () => {
    if (refreshing.current) return;
    refreshing.current = true;
    try {
      const latest = await api<ResourceDetail>(path);
      if (!mounted.current) return;
      const previous = status.current;
      status.current = latest.processing_status;
      setResource((value) => ({ ...value, ...latest }));
      setError(undefined);
      if (previous !== latest.processing_status && !isProcessing(latest)) {
        setMessage("Traitement terminé : " + latest.processing_label + ".");
        void loadSegments();
      }
    } catch (e) {
      if (mounted.current) setError(e);
    } finally {
      refreshing.current = false;
    }
  }, [path, loadSegments]);
  const processing = isProcessing(resource);
  useEffect(() => {
    if (!processing) return;
    const poll = setInterval(() => void refresh(), 4000);
    const visible = () => {
      if (document.visibilityState === "visible") void refresh();
    };
    document.addEventListener("visibilitychange", visible);
    return () => {
      clearInterval(poll);
      document.removeEventListener("visibilitychange", visible);
    };
  }, [processing, refresh]);
  useEffect(() => {
    if (!focusAfterEdit.current) return;
    document.getElementById(focusAfterEdit.current)?.focus();
    focusAfterEdit.current = null;
  });
  const findCurrent = useCallback(() => {
    const player = audio.current;
    if (!player || !segments) return;
    const time = player.currentTime;
    const index = segments.findIndex((segment, i) => {
      const from = segment.start_seconds ?? 0;
      const to =
        segment.end_seconds ?? segments[i + 1]?.start_seconds ?? Infinity;
      return time >= from && time < to;
    });
    setCurrent(index);
  }, [segments]);
  const seekFromLink = useCallback(() => {
    const player = audio.current;
    if (!player || start === null || applied.current === start) return;
    applied.current = start;
    player.currentTime = Number.isFinite(player.duration)
      ? Math.min(start, player.duration)
      : start;
    findCurrent();
  }, [start, findCurrent]);
  useEffect(() => {
    if (audio.current && audio.current.readyState >= 1) seekFromLink();
  }, [seekFromLink]);
  function play(segment: Segment) {
    const player = audio.current;
    if (!player) return;
    player.currentTime = segment.start_seconds ?? 0;
    void player.play().catch(() => undefined);
    findCurrent();
  }
  async function reprocess() {
    if (locked.current) return;
    locked.current = true;
    setBusy(true);
    setError(undefined);
    try {
      const latest = await api<Resource>(
        "courses/" + courseId + "/resources/" + resource.id + "/reprocess/",
        "POST",
        {},
      );
      status.current = latest.processing_status;
      setResource((value) => ({ ...value, ...latest }));
      setMessage("Traitement relancé : " + latest.processing_label + ".");
      if (!isProcessing(latest)) void loadSegments();
    } catch (e) {
      setError(e);
    } finally {
      locked.current = false;
      setBusy(false);
    }
  }
  function saved(segment: Segment) {
    setSegments((items) =>
      items
        ? items.map((item) => (item.id === segment.id ? segment : item))
        : items,
    );
    focusAfterEdit.current = "course-segment-" + segment.id + "-edit";
    setEditing(null);
    setMessage("Correction enregistrée.");
  }
  function cancel(segment: Segment) {
    focusAfterEdit.current = "course-segment-" + segment.id + "-edit";
    setEditing(null);
  }
  const pdf = resource.kind === "PDF";
  const location = (segment: Segment) =>
    pdf
      ? "page " + (segment.page ?? segment.order)
      : "passage de " + clock(segment.start_seconds ?? 0);
  const segmentBody = (segment: Segment) =>
    editing === segment.id ? (
      <SegmentEditor
        segment={segment}
        path={path}
        label={location(segment)}
        onSaved={saved}
        onCancel={() => cancel(segment)}
      />
    ) : (
      <>
        {segment.edited && (
          <div className="course-badges">
            <Badge>Corrigé</Badge>
            {segment.edited_at && (
              <small className="course-muted">
                le {date(segment.edited_at)}
              </small>
            )}
          </div>
        )}
        <p className="course-segment-text">{segment.text}</p>
        {editable && (
          <button
            id={"course-segment-" + segment.id + "-edit"}
            className="text-button"
            onClick={() => setEditing(segment.id)}
          >
            Corriger
            <span className="visually-hidden">
              {" "}
              le texte {pdf ? "de la " : "du "}
              {location(segment)}
            </span>
          </button>
        )}
      </>
    );
  const noText = pdf
    ? "Ce document ne contient pas de texte exploitable : il reste consultable mais n’est pas indexé pour la recherche."
    : "Aucune parole n’a été détectée dans cet enregistrement.";
  return (
    <div className="course-module">
      <div className="page-heading">
        <div>
          <p className="eyebrow">
            {pdf ? "DOCUMENT DU COURS" : "ENREGISTREMENT DU COURS"}
          </p>
          <h1>{resource.title}</h1>
          <p className="course-breadcrumb">
            {courseTitle}
            {chapterTitle && (
              <>
                <span aria-hidden="true"> › </span>
                <span className="visually-hidden">, chapitre : </span>
                {chapterTitle}
              </>
            )}
          </p>
        </div>
        <Link className="text-button" to={base + "/" + courseId}>
          Revenir au cours ↗
        </Link>
      </div>
      <p
        className="visually-hidden"
        role="status"
        aria-live="polite"
        aria-atomic="true"
      >
        {message}
      </p>
      <Alert error={error} />
      <section
        className="panel course-introduction"
        aria-label="Informations sur la ressource"
      >
        <div className="course-badges">
          <Badge>{resource.kind_label}</Badge>
          <Badge>{resource.processing_label}</Badge>
          {resource.viewed && <Badge>Consulté</Badge>}
        </div>
        <dl className="course-facts">
          <div>
            <dt>Chapitre</dt>
            <dd>{chapterTitle || "—"}</dd>
          </div>
          <div>
            <dt>Fichier</dt>
            <dd>{resource.original_name}</dd>
          </div>
          <div>
            <dt>Taille</dt>
            <dd>{fileSize(resource.size)}</dd>
          </div>
          {pdf ? (
            <div>
              <dt>Pages</dt>
              <dd>{resource.page_count ?? "—"}</dd>
            </div>
          ) : (
            <div>
              <dt>Durée</dt>
              <dd>
                {resource.duration_seconds
                  ? clock(resource.duration_seconds)
                  : "Inconnue"}
              </dd>
            </div>
          )}
          {resource.language && (
            <div>
              <dt>Langue</dt>
              <dd>{resource.language.toUpperCase()}</dd>
            </div>
          )}
        </dl>
        {resource.description && (
          <p className="course-description">{resource.description}</p>
        )}
        {processing && (
          <p className="notice course-processing-notice">
            <span className="ti-reload" aria-hidden="true" />{" "}
            {pdf
              ? "Extraction du texte en cours."
              : "Transcription en cours ou en attente."}{" "}
            Cette page s’actualise automatiquement.
          </p>
        )}
        {resource.processing_status === "NO_TEXT" && (
          <p className="notice">
            {(!student && resource.processing_error) || noText}
          </p>
        )}
        {resource.processing_status === "FAILED" && (
          <div className="notice notice-error">
            <p>
              {student
                ? "Le texte de cette ressource n’est pas disponible pour le moment. Le fichier reste consultable."
                : resource.processing_error ||
                  "Le traitement a échoué. Réessayez plus tard."}
            </p>
            {editable && (
              <button
                className="text-button"
                aria-disabled={busy || undefined}
                onClick={() => void reprocess()}
              >
                Relancer le traitement
              </button>
            )}
          </div>
        )}
        {!student && resource.job && (
          <details className="course-job">
            <summary>Détails du dernier traitement</summary>
            <dl className="course-facts">
              <div>
                <dt>État</dt>
                <dd>{resource.job.status_label}</dd>
              </div>
              <div>
                <dt>Tentatives</dt>
                <dd>{resource.job.attempts}</dd>
              </div>
              {resource.job.provider && (
                <div>
                  <dt>Service</dt>
                  <dd>
                    {resource.job.provider}
                    {resource.job.model_name
                      ? " · " + resource.job.model_name
                      : ""}
                  </dd>
                </div>
              )}
              {resource.job.processing_ms != null && (
                <div>
                  <dt>Durée du traitement</dt>
                  <dd>{seconds(resource.job.processing_ms / 1000)}</dd>
                </div>
              )}
              {resource.job.audio_seconds != null && (
                <div>
                  <dt>Audio traité</dt>
                  <dd>{clock(resource.job.audio_seconds)}</dd>
                </div>
              )}
              {resource.job.segments_count != null && (
                <div>
                  <dt>Segments produits</dt>
                  <dd>{resource.job.segments_count}</dd>
                </div>
              )}
              {resource.job.finished_at && (
                <div>
                  <dt>Terminé le</dt>
                  <dd>{date(resource.job.finished_at)}</dd>
                </div>
              )}
            </dl>
          </details>
        )}
      </section>
      {pdf ? (
        <section className="panel course-viewer" aria-label="Document PDF">
          <div className="panel-heading">
            <h2>Document</h2>
            <div className="actions">
              <a
                className="text-button"
                href={resource.file_url}
                target="_blank"
                rel="noopener"
              >
                Ouvrir dans un nouvel onglet ↗
              </a>
              <a className="text-button" href={resource.download_url}>
                Télécharger
              </a>
            </div>
          </div>
          <iframe
            className="course-pdf-frame"
            title={"Document PDF : " + resource.title}
            src={resource.file_url + (page ? "#page=" + page : "")}
          />
          <details className="course-extracted">
            <summary>
              Texte extrait
              {segments ? ` (${plural(segments.length, "page", "pages")})` : ""}
            </summary>
            <p className="field-help">
              Le texte reconnu dans le document, page par page.
              {editable
                ? " Corrigez-le si l’extraction a mal lu un passage : la recherche et l’assistant utiliseront la version corrigée."
                : ""}
            </p>
            <SegmentState
              segments={segments}
              error={segmentsError}
              onRetry={loadSegments}
              empty={
                processing
                  ? "Le texte sera disponible à la fin de l’extraction."
                  : "Aucun texte extrait pour ce document."
              }
            />
            {!!segments?.length && (
              <ol className="course-segment-list">
                {segments.map((segment) => (
                  <li
                    key={segment.id}
                    aria-current={
                      page !== null && segment.page === page
                        ? "true"
                        : undefined
                    }
                  >
                    <h3>Page {segment.page ?? segment.order}</h3>
                    {segmentBody(segment)}
                  </li>
                ))}
              </ol>
            )}
          </details>
        </section>
      ) : (
        <section
          className="panel course-viewer"
          aria-label="Enregistrement audio"
        >
          <div className="panel-heading">
            <h2>Enregistrement</h2>
            <a className="text-button" href={resource.download_url}>
              Télécharger
            </a>
          </div>
          <audio
            ref={audio}
            className="course-audio"
            controls
            preload="metadata"
            src={resource.file_url}
            onLoadedMetadata={seekFromLink}
            onTimeUpdate={findCurrent}
            onSeeked={findCurrent}
          >
            Votre navigateur ne peut pas lire cet enregistrement.{" "}
            <a href={resource.download_url}>Téléchargez-le</a>.
          </audio>
          <h3>Transcription</h3>
          <p className="field-help">
            Choisissez un horodatage pour écouter le passage correspondant.
            {editable
              ? " Corrigez la transcription si un mot a été mal reconnu."
              : ""}
          </p>
          <SegmentState
            segments={segments}
            error={segmentsError}
            onRetry={loadSegments}
            empty={
              processing
                ? "La transcription sera disponible à la fin du traitement."
                : "Aucune transcription pour cet enregistrement."
            }
          />
          {!!segments?.length && (
            <ol className="course-transcript">
              {segments.map((segment, index) => (
                <li
                  key={segment.id}
                  className={
                    "course-transcript-item" +
                    (index === current ? " is-current" : "")
                  }
                  aria-current={index === current ? "true" : undefined}
                >
                  <button
                    type="button"
                    className="course-timestamp"
                    aria-label={
                      "Écouter à partir de " +
                      spokenDuration(segment.start_seconds ?? 0)
                    }
                    onClick={() => play(segment)}
                  >
                    {clock(segment.start_seconds ?? 0)}
                  </button>
                  <div className="course-segment-body">
                    {segmentBody(segment)}
                  </div>
                </li>
              ))}
            </ol>
          )}
        </section>
      )}
    </div>
  );
}
function SegmentState({
  segments,
  error,
  onRetry,
  empty,
}: {
  segments: Segment[] | null;
  error: unknown;
  onRetry: () => void;
  empty: string;
}) {
  if (error)
    return (
      <div>
        <Alert error={error} />
        <button className="text-button" onClick={onRetry}>
          Réessayer le chargement du texte
        </button>
      </div>
    );
  if (!segments) return <Loading />;
  return segments.length ? null : <p className="course-muted">{empty}</p>;
}
function SegmentEditor({
  segment,
  path,
  label,
  onSaved,
  onCancel,
}: {
  segment: Segment;
  path: string;
  label: string;
  onSaved: (segment: Segment) => void;
  onCancel: () => void;
}) {
  const [text, setText] = useState(segment.text),
    [error, setError] = useState<unknown>(),
    [busy, setBusy] = useState(false);
  const locked = useRef(false);
  const validation = useFormValidation(() => validateSegment(text), { text });
  async function save(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (locked.current) return;
    setError(undefined);
    try {
      validation.check();
    } catch (issue) {
      setError(issue);
      return;
    }
    locked.current = true;
    setBusy(true);
    try {
      const updated = await api<Segment>(
        path + "segments/" + segment.id + "/",
        "PATCH",
        { text: text.trim() },
      );
      onSaved(updated);
    } catch (issue) {
      validation.serverErrors(issue);
      setError(issue);
    } finally {
      locked.current = false;
      setBusy(false);
    }
  }
  return (
    <form
      className="course-segment-form"
      noValidate
      onSubmit={save}
      ref={validation.formProps.formRef}
      onBlur={validation.formProps.onBlur}
      onKeyDown={(e) => {
        if (e.key === "Escape") {
          e.preventDefault();
          onCancel();
        }
      }}
    >
      <Alert error={error} />
      <Textarea
        label={"Texte corrigé, " + label}
        name="text"
        rows={6}
        value={text}
        required
        maxLength={SEGMENT_MAX_LENGTH}
        autoFocus
        error={validation.errors.text}
        onChange={(e) => setText(e.target.value)}
      />
      <div className="actions">
        <button className="btn_one" aria-disabled={busy || undefined}>
          {busy ? "Enregistrement…" : "Enregistrer la correction"}
        </button>
        <button type="button" className="text-button" onClick={onCancel}>
          Annuler
        </button>
      </div>
    </form>
  );
}
