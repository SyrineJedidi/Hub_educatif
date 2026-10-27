import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { allPages, query } from "../api/client";
import { useResource } from "../hooks/useResource";
import type { Page, User } from "../api/types";
import {
  Alert,
  Badge,
  Empty,
  Field,
  Loading,
  Pagination,
  Select,
} from "../components/UI";
import { useCourseContext } from "./useCourseContext";
import { courseStatuses } from "./types";
import type { Course, Subject, SubjectSummary } from "./types";
import { personName, plural } from "./format";
import { CourseProgress } from "./ChapterSection";
import "./courses.css";
export default function CourseList() {
  const { student } = useCourseContext();
  return student ? <StudentCourses /> : <ManagedCourses />;
}
function StudentCourses() {
  const { base, apiBase } = useCourseContext();
  const [q, setQ] = useState(""),
    [subject, setSubject] = useState(""),
    [page, setPage] = useState(1),
    [subjects, setSubjects] = useState<SubjectSummary[]>([]);
  const { data, error, loading, reload } = useResource<Page<Course>>(
    apiBase + "?" + query({ q, subject, page }),
  );
  // Students cannot list subjects: the filter grows with the courses already loaded.
  useEffect(() => {
    if (!data) return;
    setSubjects((known) => {
      const all = new Map(known.map((item) => [item.id, item]));
      for (const course of data.results)
        all.set(course.subject.id, course.subject);
      return [...all.values()].sort((a, b) =>
        a.name.localeCompare(b.name, "fr"),
      );
    });
  }, [data]);
  const filtered = !!(q || subject);
  function reset() {
    setQ("");
    setSubject("");
    setPage(1);
  }
  return (
    <div className="course-module">
      <div className="page-heading">
        <div>
          <p className="eyebrow">COURS ET RESSOURCES</p>
          <h1>Mes cours</h1>
          <p>
            Retrouvez les supports de vos enseignants, chapitre par chapitre, et
            suivez les ressources déjà consultées.
          </p>
        </div>
        <Link className="text-button" to={base + "/recherche"}>
          Rechercher dans mes cours ↗
        </Link>
      </div>
      <section
        className="panel course-filters"
        aria-label="Rechercher et filtrer les cours"
      >
        <div className="filters">
          <Field
            label="Rechercher par titre"
            type="search"
            value={q}
            maxLength={100}
            onChange={(e) => {
              setQ(e.target.value);
              setPage(1);
            }}
          />
          <Select
            label="Matière"
            value={subject}
            onChange={(e) => {
              setSubject(e.target.value);
              setPage(1);
            }}
          >
            <option value="">Toutes les matières</option>
            {subjects.map((item) => (
              <option key={item.id} value={item.id}>
                {item.name}
              </option>
            ))}
          </Select>
        </div>
        {filtered && (
          <button className="text-button" onClick={reset}>
            Réinitialiser les filtres
          </button>
        )}
      </section>
      <Alert error={error} />
      {loading ? (
        <Loading />
      ) : !data ? (
        <button className="text-button" onClick={reload}>
          Réessayer le chargement
        </button>
      ) : data.results.length ? (
        <>
          <p className="field-help" role="status">
            {plural(data.count, "cours", "cours")}{" "}
            {filtered
              ? data.count > 1
                ? "correspondent à vos filtres"
                : "correspond à vos filtres"
              : data.count > 1
                ? "disponibles pour vos groupes"
                : "disponible pour vos groupes"}
            .
          </p>
          <div className="course-card-grid">
            {data.results.map((course) => (
              <article className="panel course-card" key={course.id}>
                <span className="ti-book course-card-icon" aria-hidden="true" />
                <div className="course-badges">
                  <Badge>{course.subject.name}</Badge>
                </div>
                <h2>
                  <Link to={base + "/" + course.id}>{course.title}</Link>
                </h2>
                <p className="course-muted">
                  Enseignant : {personName(course.teacher)}
                </p>
                <p className="course-description">{course.description}</p>
                <dl className="course-facts">
                  <div>
                    <dt>Chapitres</dt>
                    <dd>{course.chapters_count}</dd>
                  </div>
                  <div>
                    <dt>Ressources</dt>
                    <dd>{course.resources_count}</dd>
                  </div>
                </dl>
                <CourseProgress
                  progress={course.progress}
                  label={"Ressources consultées : " + course.title}
                />
                <Link className="btn_one" to={base + "/" + course.id}>
                  Ouvrir le cours
                  <span className="visually-hidden"> {course.title}</span> ↗
                </Link>
              </article>
            ))}
          </div>
          <Pagination page={page} count={data.count} onChange={setPage} />
        </>
      ) : (
        <section className="panel">
          <Empty
            headingLevel={2}
            title={filtered ? "Aucun résultat" : "Aucun cours pour le moment"}
          >
            {filtered
              ? "Aucun cours ne correspond à ces critères. Modifiez la recherche ou réinitialisez les filtres."
              : "Aucun cours publié pour vos groupes pour le moment."}
          </Empty>
          <div className="course-empty-action">
            {filtered ? (
              <button className="btn_one" onClick={reset}>
                Afficher tous mes cours
              </button>
            ) : (
              <Link className="text-button" to="/espace/groupes">
                Voir mes groupes ↗
              </Link>
            )}
          </div>
        </section>
      )}
    </div>
  );
}
function ManagedCourses() {
  const { base, subjects: subjectsPath, admin } = useCourseContext();
  const [q, setQ] = useState(""),
    [status, setStatus] = useState(""),
    [subject, setSubject] = useState(""),
    [teacher, setTeacher] = useState(""),
    [page, setPage] = useState(1);
  const [subjects, setSubjects] = useState<Subject[]>([]),
    [teachers, setTeachers] = useState<User[]>([]),
    [filterError, setFilterError] = useState<unknown>();
  useEffect(() => {
    let active = true;
    allPages<Subject>("subjects/")
      .then((items) => {
        if (active) setSubjects(items);
      })
      .catch((e) => {
        if (active) setFilterError(e);
      });
    if (admin)
      allPages<User>("admin/users/?role=TEACHER")
        .then((items) => {
          if (active) setTeachers(items);
        })
        .catch((e) => {
          if (active) setFilterError(e);
        });
    return () => {
      active = false;
    };
  }, [admin]);
  const { data, error, loading, reload } = useResource<Page<Course>>(
    "courses/?" + query({ q, status, subject, teacher, page }),
  );
  const filtered = !!(q || status || subject || teacher);
  function filter(setter: (value: string) => void, value: string) {
    setter(value);
    setPage(1);
  }
  function reset() {
    setQ("");
    setStatus("");
    setSubject("");
    setTeacher("");
    setPage(1);
  }
  return (
    <div className="course-module">
      <div className="page-heading">
        <div>
          <p className="eyebrow">COURS ET RESSOURCES</p>
          <h1>Gestion des cours</h1>
          <p>
            Organisez vos cours en chapitres, importez vos PDF et vos
            enregistrements, puis publiez-les pour vos groupes.
          </p>
        </div>
        <div className="course-heading-links">
          <Link className="btn_one" to={base + "/nouveau"}>
            Créer un cours +
          </Link>
          <Link className="text-button" to={subjectsPath}>
            Matières ↗
          </Link>
          <Link className="text-button" to={base + "/recherche"}>
            Rechercher dans les cours ↗
          </Link>
        </div>
      </div>
      <section
        className="panel course-filters"
        aria-label="Rechercher et filtrer les cours"
      >
        <div className="filters">
          <Field
            label="Rechercher par titre"
            type="search"
            value={q}
            maxLength={100}
            onChange={(e) => filter(setQ, e.target.value)}
          />
          <Select
            label="Statut"
            value={status}
            onChange={(e) => filter(setStatus, e.target.value)}
          >
            <option value="">Tous les statuts</option>
            {Object.entries(courseStatuses).map(([key, label]) => (
              <option key={key} value={key}>
                {label}
              </option>
            ))}
          </Select>
          <Select
            label="Matière"
            value={subject}
            onChange={(e) => filter(setSubject, e.target.value)}
          >
            <option value="">Toutes les matières</option>
            {subjects.map((item) => (
              <option key={item.id} value={item.id}>
                {item.name} · {item.code}
              </option>
            ))}
          </Select>
          {admin && (
            <Select
              label="Enseignant"
              value={teacher}
              onChange={(e) => filter(setTeacher, e.target.value)}
            >
              <option value="">Tous les enseignants</option>
              {teachers.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.first_name} {item.last_name}
                </option>
              ))}
            </Select>
          )}
        </div>
        {filtered && (
          <button className="text-button" onClick={reset}>
            Réinitialiser les filtres
          </button>
        )}
        <Alert error={filterError} />
      </section>
      {loading ? (
        <Loading />
      ) : error || !data ? (
        <section className="panel">
          <Alert error={error} />
          <button className="text-button" onClick={reload}>
            Réessayer le chargement
          </button>
        </section>
      ) : data.results.length ? (
        <section className="panel">
          <div className="panel-heading">
            <h2>{plural(data.count, "cours", "cours")}</h2>
            <button className="text-button" onClick={reload}>
              Actualiser la liste
            </button>
          </div>
          <div
            className="table-scroll course-table-scroll"
            role="region"
            aria-label="Liste des cours"
            tabIndex={0}
          >
            <table className="course-table">
              <caption className="visually-hidden">
                {filtered
                  ? "Cours correspondant aux filtres"
                  : "Cours de votre espace"}
              </caption>
              <thead>
                <tr>
                  <th scope="col">Cours</th>
                  <th scope="col">Matière</th>
                  <th scope="col">Groupes</th>
                  <th scope="col">Statut</th>
                  <th scope="col">Contenu</th>
                  <th scope="col">Actions</th>
                </tr>
              </thead>
              <tbody>
                {data.results.map((course) => (
                  <tr key={course.id}>
                    <th scope="row">
                      <Link to={base + "/" + course.id}>{course.title}</Link>
                      {admin && <small>{personName(course.teacher)}</small>}
                    </th>
                    <td>
                      {course.subject.name}
                      <small>{course.subject.code}</small>
                    </td>
                    <td>
                      {course.groups?.length
                        ? course.groups.map((group) => group.name).join(", ")
                        : "Aucun groupe"}
                    </td>
                    <td>
                      <Badge>
                        {course.status_label ||
                          (course.status && courseStatuses[course.status])}
                      </Badge>
                    </td>
                    <td>
                      {plural(course.chapters_count, "chapitre", "chapitres")}
                      <small>
                        {plural(
                          course.resources_count,
                          "ressource",
                          "ressources",
                        )}
                      </small>
                      {!!course.processing_count && (
                        <small className="course-processing">
                          <span className="ti-reload" aria-hidden="true" />{" "}
                          {course.processing_count} en traitement
                        </small>
                      )}
                    </td>
                    <td>
                      <div className="course-row-actions">
                        <Link
                          className="text-button"
                          to={base + "/" + course.id}
                        >
                          Ouvrir
                          <span className="visually-hidden">
                            {" "}
                            le cours {course.title}
                          </span>
                        </Link>
                        {course.status !== "ARCHIVED" && (
                          <Link
                            className="text-button"
                            to={base + "/" + course.id + "/modifier"}
                          >
                            Modifier
                            <span className="visually-hidden">
                              {" "}
                              le cours {course.title}
                            </span>
                          </Link>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <Pagination page={page} count={data.count} onChange={setPage} />
        </section>
      ) : (
        <section className="panel">
          <Empty
            headingLevel={2}
            title={
              filtered ? "Aucun résultat" : "Votre premier cours vous attend"
            }
          >
            {filtered
              ? "Aucun cours ne correspond à ces critères. Modifiez la recherche ou réinitialisez les filtres."
              : "Créez un brouillon, ajoutez vos chapitres et importez vos supports, à votre rythme."}
          </Empty>
          <div className="course-empty-action">
            {filtered ? (
              <button className="btn_one" onClick={reset}>
                Afficher tous les cours
              </button>
            ) : (
              <Link className="btn_one" to={base + "/nouveau"}>
                Créer mon premier cours +
              </Link>
            )}
          </div>
        </section>
      )}
    </div>
  );
}
