import { useCallback, useEffect, useId, useRef, useState } from "react";
import { Link, useLocation, useParams } from "react-router-dom";
import { api, ApiError, date } from "../api/client";
import { useResource } from "../hooks/useResource";
import { Alert, Badge, Empty, Loading, Modal } from "../components/UI";
import type { Chapter, Course, ProcessingInfo, Resource } from "./types";
import { courseStatuses, courseVisibility, isProcessing } from "./types";
import { personName, plural } from "./format";
import { useCourseContext } from "./useCourseContext";
import { CourseUnavailable } from "./CourseRoutes";
import CourseActions from "./CourseActions";
import ChapterSection, {
  ChapterForm,
  CourseProgress,
  useMoveFocus,
} from "./ChapterSection";
import "./courses.css";
// The router does not scroll to a fragment, and search results link to #chapitre-<id>.
function useChapterTarget() {
  const { hash } = useLocation();
  useEffect(() => {
    const target = hash ? document.getElementById(hash.slice(1)) : null;
    if (!target) return;
    target.scrollIntoView({ block: "start" });
    target.focus({ preventScroll: true });
  }, [hash]);
}
export default function CourseDetail() {
  const { id } = useParams(),
    { apiBase, student } = useCourseContext();
  const { data, error, loading, reload } = useResource<Course>(
    apiBase + id + "/",
  );
  if (loading) return <Loading />;
  if (!data) return <CourseUnavailable error={error} onRetry={reload} />;
  return student ? (
    <StudentCourse course={data} />
  ) : (
    <ManagedCourse key={data.id} initial={data} />
  );
}
function StudentCourse({ course }: { course: Course }) {
  const { base } = useCourseContext();
  const heading = useId();
  useChapterTarget();
  const chapters = course.chapters || [];
  return (
    <div className="course-module">
      <div className="page-heading">
        <div>
          <p className="eyebrow">MES COURS · {course.subject.code}</p>
          <h1>{course.title}</h1>
          <p>
            {course.subject.name} · {personName(course.teacher)}
          </p>
        </div>
        <div className="course-heading-links">
          <Link className="text-button" to={base}>
            Tous mes cours ↗
          </Link>
          <Link
            className="text-button"
            to={base + "/recherche?course=" + course.id}
          >
            Rechercher dans ce cours ↗
          </Link>
        </div>
      </div>
      <section
        className="panel course-introduction"
        aria-label="Présentation du cours"
      >
        <dl className="course-facts">
          <div>
            <dt>Matière</dt>
            <dd>{course.subject.name}</dd>
          </div>
          <div>
            <dt>Enseignant</dt>
            <dd>{personName(course.teacher)}</dd>
          </div>
          <div>
            <dt>Contenu</dt>
            <dd>
              {plural(course.chapters_count, "chapitre", "chapitres")} ·{" "}
              {plural(course.resources_count, "ressource", "ressources")}
            </dd>
          </div>
        </dl>
        <p className="course-description">{course.description}</p>
        <CourseProgress
          progress={course.progress}
          label="Ressources consultées dans ce cours"
        />
      </section>
      <section className="course-chapters" aria-labelledby={heading}>
        <h2 id={heading} className="course-section-title">
          Chapitres
        </h2>
        {chapters.length ? (
          chapters.map((chapter, index) => (
            <ChapterSection
              key={chapter.id}
              courseId={course.id}
              chapter={chapter}
              index={index}
            />
          ))
        ) : (
          <section className="panel">
            <Empty title="Aucun chapitre pour le moment">
              Votre enseignant n’a pas encore ajouté de chapitre à ce cours.
            </Empty>
          </section>
        )}
      </section>
    </div>
  );
}
const statusMap = (course: Course) =>
  new Map(
    (course.chapters || []).flatMap((chapter) =>
      chapter.resources.map((r) => [r.id, r.processing_status] as const),
    ),
  );
function ManagedCourse({ initial }: { initial: Course }) {
  const { base } = useCourseContext();
  const heading = useId();
  useChapterTarget();
  const [course, setCourse] = useState(initial),
    [error, setError] = useState<unknown>(),
    [denied, setDenied] = useState(false),
    [processing, setProcessing] = useState<ProcessingInfo | null>(null),
    [message, setMessage] = useState(""),
    [busy, setBusy] = useState(false),
    [adding, setAdding] = useState(false);
  const mounted = useRef(true),
    refreshing = useRef(false),
    again = useRef(false),
    locked = useRef(false),
    statuses = useRef(statusMap(initial));
  const focusMove = useMoveFocus();
  const refresh = useCallback(async () => {
    // A refresh requested during another one runs right after it, so writes are never lost.
    if (refreshing.current) {
      again.current = true;
      return;
    }
    refreshing.current = true;
    try {
      do {
        again.current = false;
        const latest = await api<Course>("courses/" + initial.id + "/");
        if (!mounted.current) return;
        const changes: string[] = [];
        for (const chapter of latest.chapters || [])
          for (const r of chapter.resources) {
            const previous = statuses.current.get(r.id);
            if (
              previous &&
              previous !== r.processing_status &&
              !isProcessing(r)
            )
              changes.push(`« ${r.title} » : ${r.processing_label}.`);
          }
        statuses.current = statusMap(latest);
        if (changes.length) setMessage(changes.join(" "));
        setCourse(latest);
        setError(undefined);
      } while (again.current);
    } catch (e) {
      if (mounted.current) {
        setError(e);
        if (e instanceof ApiError && [401, 403, 404].includes(e.status))
          setDenied(true);
      }
    } finally {
      refreshing.current = false;
    }
  }, [initial.id]);
  const chapters = course.chapters || [];
  const resources = chapters.flatMap((chapter) => chapter.resources);
  const active = resources.filter(isProcessing);
  const polling = active.length > 0 && !denied;
  const archived = course.status === "ARCHIVED";
  useEffect(() => {
    mounted.current = true;
    let live = true;
    api<ProcessingInfo>("courses/processing/")
      .then((info) => {
        if (live) setProcessing(info);
      })
      .catch(() => undefined);
    return () => {
      live = false;
      mounted.current = false;
    };
  }, []);
  useEffect(() => {
    const visible = () => {
      if (document.visibilityState === "visible" && !denied) void refresh();
    };
    document.addEventListener("visibilitychange", visible);
    const poll = polling ? setInterval(() => void refresh(), 4000) : undefined;
    return () => {
      document.removeEventListener("visibilitychange", visible);
      if (poll) clearInterval(poll);
    };
  }, [polling, denied, refresh]);
  async function moveChapter(index: number, offset: number) {
    const target = index + offset;
    if (locked.current || target < 0 || target >= chapters.length) return;
    locked.current = true;
    setBusy(true);
    setError(undefined);
    const ids = chapters.map((chapter) => chapter.id);
    [ids[index], ids[target]] = [ids[target], ids[index]];
    try {
      const result = await api<{ results: Chapter[] }>(
        "courses/" + course.id + "/chapters/reorder/",
        "POST",
        { chapter_ids: ids },
      );
      if (!mounted.current) return;
      // A poll started before the move would bring back the old order.
      if (refreshing.current) again.current = true;
      focusMove("course-chapter-" + chapters[index].id, offset < 0);
      setCourse((current) => ({
        ...current,
        chapters: result.results.map((chapter) => ({
          ...chapter,
          resources:
            chapter.resources ||
            current.chapters?.find((c) => c.id === chapter.id)?.resources ||
            [],
        })),
      }));
      setMessage(
        `Chapitre « ${chapters[index].title} » déplacé en position ${target + 1}.`,
      );
    } catch (e) {
      if (mounted.current) setError(e);
    } finally {
      locked.current = false;
      setBusy(false);
    }
  }
  function setResources(chapterId: string, items: Resource[]) {
    if (refreshing.current) again.current = true;
    setCourse((current) => ({
      ...current,
      chapters: current.chapters?.map((chapter) =>
        chapter.id === chapterId ? { ...chapter, resources: items } : chapter,
      ),
    }));
  }
  const waitingAudio = active.some((r) => r.kind === "AUDIO");
  return (
    <div className="course-module">
      <div className="page-heading">
        <div>
          <p className="eyebrow">ATELIER DE COURS · {course.subject.code}</p>
          <h1>{course.title}</h1>
          <div className="course-badges">
            <Badge>
              {course.status_label ||
                (course.status && courseStatuses[course.status])}
            </Badge>
            <Badge>{course.subject.name}</Badge>
          </div>
        </div>
        <Link className="text-button" to={base}>
          Tous les cours ↗
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
      {denied && (
        <button
          className="text-button"
          onClick={() => window.location.reload()}
        >
          Recharger la page
        </button>
      )}
      <section
        className="panel course-introduction"
        aria-label="Présentation du cours"
      >
        <dl className="course-facts">
          <div>
            <dt>Matière</dt>
            <dd>
              {course.subject.name} · {course.subject.code}
            </dd>
          </div>
          <div>
            <dt>Enseignant</dt>
            <dd>{personName(course.teacher)}</dd>
          </div>
          <div>
            <dt>Groupes</dt>
            <dd>
              {course.groups?.length
                ? course.groups
                    .map((g) => g.name + (g.archived ? " (archivé)" : ""))
                    .join(", ")
                : "Aucun groupe"}
            </dd>
          </div>
          <div>
            <dt>Chapitres</dt>
            <dd>{course.chapters_count}</dd>
          </div>
          <div>
            <dt>Ressources</dt>
            <dd>{course.resources_count}</dd>
          </div>
          <div>
            <dt>Première publication</dt>
            <dd>
              {course.published_at
                ? date(course.published_at)
                : "Jamais publié"}
            </dd>
          </div>
        </dl>
        <p className="course-description">{course.description}</p>
        {course.status && (
          <p className="field-help">
            <strong>Visibilité : </strong>
            {courseVisibility[course.status]}
          </p>
        )}
        <div className="actions">
          {!archived && (
            <Link
              className="text-button"
              to={base + "/" + course.id + "/modifier"}
            >
              Modifier la présentation
            </Link>
          )}
          <Link
            className="text-button"
            to={base + "/" + course.id + "/statistiques"}
          >
            Statistiques ↗
          </Link>
          <Link
            className="text-button"
            to={base + "/recherche?course=" + course.id}
          >
            Rechercher dans ce cours ↗
          </Link>
        </div>
        <CourseActions course={course} onDone={() => void refresh()} />
        {archived && (
          <p className="notice">
            Ce cours est archivé : il est en lecture seule et masqué aux
            étudiants. Restaurez-le pour le modifier.
          </p>
        )}
      </section>
      {waitingAudio && processing && !processing.configured && (
        <p className="notice notice-error">
          La transcription automatique n’est pas configurée sur ce serveur : les
          enregistrements audio restent consultables mais ne seront pas
          transcrits. Contactez l’administrateur de la plateforme.
        </p>
      )}
      {active.length > 0 && (
        <p className="notice course-processing-notice">
          <span className="ti-reload" aria-hidden="true" />{" "}
          {plural(active.length, "ressource", "ressources")} en cours de
          traitement. Cette page s’actualise automatiquement.
        </p>
      )}
      <section className="course-chapters" aria-labelledby={heading}>
        <div className="panel-heading course-section-heading">
          <h2 id={heading}>Chapitres du cours</h2>
          {!archived && (
            <button className="btn_one" onClick={() => setAdding(true)}>
              Ajouter un chapitre +
            </button>
          )}
        </div>
        {chapters.length ? (
          chapters.map((chapter, index) => (
            <ChapterSection
              key={chapter.id}
              courseId={course.id}
              chapter={chapter}
              index={index}
              manager={{
                count: chapters.length,
                chapters,
                editable: !archived,
                busy,
                onMove: (offset) => void moveChapter(index, offset),
                onChanged: () => void refresh(),
                onResources: setResources,
                announce: setMessage,
              }}
            />
          ))
        ) : (
          <section className="panel">
            <Empty title="Aucun chapitre pour le moment">
              {archived
                ? "Ce cours archivé ne contient aucun chapitre."
                : "Ajoutez votre premier chapitre, puis importez vos PDF et vos enregistrements audio."}
            </Empty>
            {!archived && (
              <div className="course-empty-action">
                <button className="btn_one" onClick={() => setAdding(true)}>
                  Ajouter mon premier chapitre +
                </button>
              </div>
            )}
          </section>
        )}
      </section>
      {adding && (
        <Modal title="Ajouter un chapitre" onClose={() => setAdding(false)}>
          <ChapterForm
            courseId={course.id}
            onSaved={() => {
              setAdding(false);
              setMessage("Chapitre ajouté.");
              void refresh();
            }}
          />
        </Modal>
      )}
    </div>
  );
}
