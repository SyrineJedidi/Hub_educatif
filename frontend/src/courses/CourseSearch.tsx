import { useEffect, useRef, useState } from "react";
import type { FormEvent, ReactNode } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { api, allPages, query } from "../api/client";
import type { Page } from "../api/types";
import {
  Alert,
  Badge,
  Empty,
  Field,
  Loading,
  Pagination,
  Select,
} from "../components/UI";
import type { Course, SearchResult, SubjectSummary } from "./types";
import { resourceKinds, searchTypes } from "./types";
import { clock, plural } from "./format";
import { useCourseContext } from "./useCourseContext";
import "./courses.css";
const MIN_QUERY = 2;
// The API counts offsets in code points; a UTF-16 slice would drift after 𝑓 or an emoji.
function highlighted(text: string, ranges: [number, number][]) {
  const chars = Array.from(text);
  const part = (from: number, to: number) => chars.slice(from, to).join("");
  const nodes: ReactNode[] = [];
  let cursor = 0;
  [...ranges]
    .map(([from, to]) => [Math.max(0, from), Math.min(chars.length, to)])
    .filter(([from, to]) => to > from)
    .sort((a, b) => a[0] - b[0])
    .forEach(([from, to], i) => {
      if (to <= cursor) return;
      const begin = Math.max(from, cursor);
      if (begin > cursor) nodes.push(part(cursor, begin));
      nodes.push(<mark key={i}>{part(begin, to)}</mark>);
      cursor = to;
    });
  if (cursor < chars.length) nodes.push(part(cursor, chars.length));
  return nodes;
}
export default function CourseSearch() {
  const { base, admin, student } = useCourseContext();
  const [params, setParams] = useSearchParams();
  const q = params.get("q") || "",
    kind = params.get("kind") || "",
    subject = params.get("subject") || "",
    course = params.get("course") || "",
    page = Math.max(1, Number(params.get("page")) || 1);
  const [draft, setDraft] = useState(q),
    [draftKind, setDraftKind] = useState(kind),
    [draftSubject, setDraftSubject] = useState(subject),
    [queryError, setQueryError] = useState("");
  const [subjects, setSubjects] = useState<SubjectSummary[]>([]),
    [filterError, setFilterError] = useState<unknown>();
  const [data, setData] = useState<Page<SearchResult> | null>(null),
    [error, setError] = useState<unknown>(),
    [loading, setLoading] = useState(false),
    [revision, setRevision] = useState(0);
  const formRef = useRef<HTMLFormElement>(null);
  const ready = Array.from(q.trim()).length >= MIN_QUERY;
  useEffect(() => {
    setDraft(q);
    setDraftKind(kind);
    setDraftSubject(subject);
  }, [q, kind, subject]);
  useEffect(() => {
    let active = true;
    // Students cannot list subjects: offer those of the courses they can open.
    const load = student
      ? allPages<Course>("student/courses/").then((courses) =>
          [
            ...new Map(courses.map((c) => [c.subject.id, c.subject])).values(),
          ].sort((a, b) => a.name.localeCompare(b.name, "fr")),
        )
      : allPages<SubjectSummary>("subjects/");
    load
      .then((items) => {
        if (active) setSubjects(items);
      })
      .catch((e) => {
        if (active) setFilterError(e);
      });
    return () => {
      active = false;
    };
  }, [student]);
  useEffect(() => {
    if (!ready) {
      setData(null);
      setError(undefined);
      setLoading(false);
      return;
    }
    let active = true;
    setLoading(true);
    setError(undefined);
    api<Page<SearchResult>>(
      "courses/search/?" + query({ q, kind, subject, course, page }),
    )
      .then((result) => {
        if (active) setData(result);
      })
      .catch((e) => {
        if (active) {
          setData(null);
          setError(e);
        }
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [q, kind, subject, course, page, ready, revision]);
  function update(values: Record<string, string>) {
    setParams(
      Object.fromEntries(Object.entries(values).filter(([, value]) => value)),
    );
  }
  function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const value = draft.trim();
    if (Array.from(value).length < MIN_QUERY) {
      setQueryError("Saisissez au moins 2 caractères.");
      requestAnimationFrame(() =>
        formRef.current
          ?.querySelector<HTMLElement>('[aria-invalid="true"]')
          ?.focus(),
      );
      return;
    }
    setQueryError("");
    update({ q: value, kind: draftKind, subject: draftSubject, course });
  }
  const link = (result: SearchResult) => {
    if (result.link?.startsWith("/espace/cours/"))
      return admin
        ? result.link.replace(/^\/espace\/cours/u, base)
        : result.link;
    const coursePath = base + "/" + result.course.id;
    if (!result.resource) return coursePath;
    return (
      coursePath +
      "/ressources/" +
      result.resource.id +
      (result.page
        ? "?page=" + result.page
        : result.start_seconds != null
          ? "?t=" + Math.floor(result.start_seconds)
          : "")
    );
  };
  const title = (result: SearchResult) =>
    result.resource?.title || result.chapter?.title || result.course.title;
  const announcement = !ready
    ? ""
    : loading
      ? "Recherche en cours…"
      : data
        ? data.count
          ? `${plural(data.count, "résultat", "résultats")} pour « ${q} ».`
          : `Aucun résultat pour « ${q} ».`
        : "";
  return (
    <div className="course-module">
      <div className="page-heading">
        <div>
          <p className="eyebrow">COURS ET RESSOURCES</p>
          <h1>
            {admin ? "Rechercher dans les cours" : "Rechercher dans mes cours"}
          </h1>
          <p>
            La recherche porte sur les titres, les descriptions, le texte des
            PDF et les transcriptions audio, sans tenir compte des accents ni
            des majuscules.
          </p>
        </div>
        <Link className="text-button" to={base}>
          {student ? "Mes cours" : "Gestion des cours"} ↗
        </Link>
      </div>
      <section className="panel" aria-label="Formulaire de recherche">
        <form
          ref={formRef}
          role="search"
          className="course-search-form"
          noValidate
          onSubmit={submit}
        >
          <div className="filters">
            <Field
              label="Mots recherchés"
              type="search"
              name="q"
              value={draft}
              maxLength={100}
              required
              error={queryError}
              onChange={(e) => {
                setDraft(e.target.value);
                setQueryError("");
              }}
            />
            <Select
              label="Type de ressource"
              name="kind"
              value={draftKind}
              onChange={(e) => setDraftKind(e.target.value)}
            >
              <option value="">Tous</option>
              <option value="PDF">PDF</option>
              <option value="AUDIO">Audio</option>
            </Select>
            <Select
              label="Matière"
              name="subject"
              value={draftSubject}
              onChange={(e) => setDraftSubject(e.target.value)}
            >
              <option value="">Toutes les matières</option>
              {subjects.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.name}
                </option>
              ))}
            </Select>
            <button className="btn_one course-search-submit">Rechercher</button>
          </div>
        </form>
        {course && (
          <p className="notice">
            Recherche limitée à un seul cours
            {data?.results[0]
              ? ` : « ${data.results[0].course.title} »`
              : ""}.{" "}
            <button
              className="text-button"
              onClick={() => update({ q, kind, subject })}
            >
              Rechercher dans tous les cours
            </button>
          </p>
        )}
        <Alert error={filterError} />
      </section>
      <p
        className="field-help course-search-count"
        role="status"
        aria-live="polite"
        aria-atomic="true"
      >
        {announcement}
      </p>
      {!ready ? (
        <section className="panel">
          <Empty headingLevel={2} title="Que cherchez-vous ?">
            Saisissez au moins 2 caractères : un mot du cours, une notion vue en
            séance ou un passage d’un enregistrement.
          </Empty>
        </section>
      ) : loading ? (
        <Loading />
      ) : error || !data ? (
        <section className="panel">
          <Alert error={error} />
          <button
            className="text-button"
            onClick={() => setRevision((n) => n + 1)}
          >
            Relancer la recherche
          </button>
        </section>
      ) : data.results.length ? (
        <>
          <ol className="course-search-results" start={(page - 1) * 20 + 1}>
            {data.results.map((result, i) => (
              <li className="panel course-search-result" key={page + "-" + i}>
                <div className="course-badges">
                  <Badge>{searchTypes[result.type] || result.type}</Badge>
                  {result.resource && (
                    <Badge>{resourceKinds[result.resource.kind]}</Badge>
                  )}
                </div>
                <h2>
                  <Link to={link(result)}>{title(result)}</Link>
                </h2>
                <p className="course-breadcrumb">
                  {[
                    result.course.title,
                    result.chapter?.title,
                    result.resource?.title,
                  ]
                    .filter(Boolean)
                    .map((part, index) => (
                      <span key={index}>
                        {index > 0 && <span aria-hidden="true"> › </span>}
                        {index > 0 && (
                          <span className="visually-hidden">, </span>
                        )}
                        {part}
                      </span>
                    ))}
                </p>
                {result.snippet && (
                  <p className="course-snippet">
                    {highlighted(result.snippet, result.highlights || [])}
                  </p>
                )}
                {(result.page || result.start_seconds != null) && (
                  <p className="course-muted">
                    {result.page
                      ? "Page " + result.page
                      : "à " + clock(result.start_seconds ?? 0)}
                  </p>
                )}
              </li>
            ))}
          </ol>
          <Pagination
            page={page}
            count={data.count}
            onChange={(next) =>
              update({ q, kind, subject, course, page: String(next) })
            }
          />
        </>
      ) : (
        <section className="panel">
          <Empty headingLevel={2} title="Aucun résultat">
            Aucun passage ne contient tous ces mots. Essayez un mot plus court,
            retirez un filtre ou vérifiez l’orthographe.
          </Empty>
        </section>
      )}
    </div>
  );
}
