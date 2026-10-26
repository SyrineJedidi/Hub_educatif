import { Link, useParams } from "react-router-dom";
import { date } from "../api/client";
import { useResource } from "../hooks/useResource";
import { Alert, Empty, Loading } from "../components/UI";
import type { Statistics } from "./types";
import { resourceKinds } from "./types";
import { percent } from "./format";
import { useCourseContext } from "./useCourseContext";
import "./courses.css";
export default function CourseStatistics() {
  const { id } = useParams(),
    { base } = useCourseContext();
  const { data, error, loading, reload } = useResource<Statistics>(
    "courses/" + id + "/statistics/",
  );
  return (
    <div className="course-module">
      <div className="page-heading">
        <div>
          <p className="eyebrow">SUIVRE LA CONSULTATION</p>
          <h1>Statistiques du cours</h1>
          <p>
            {data?.course.title ||
              "Consultation des ressources par les étudiants inscrits."}
          </p>
        </div>
        <div className="course-heading-links">
          <Link className="text-button" to={base + "/" + id}>
            Revenir au cours ↗
          </Link>
          {data && (
            <a
              className="btn_one"
              href={"/api/courses/" + id + "/statistics/?format=csv"}
            >
              Exporter en CSV ↗
            </a>
          )}
        </div>
      </div>
      {loading ? (
        <Loading />
      ) : !data ? (
        <section className="panel">
          <Alert error={error} />
          <button className="text-button" onClick={reload}>
            Réessayer le chargement
          </button>
        </section>
      ) : (
        <>
          <div className="metric-grid">
            {(
              [
                ["ti-user", data.summary.students, "Élèves"],
                ["ti-files", data.summary.resources, "Ressources"],
                [
                  "ti-stats-up",
                  percent(data.summary.average_percent),
                  "Progression moyenne",
                ],
                [
                  "ti-check",
                  data.summary.completed_students,
                  "Élèves ayant tout consulté",
                ],
              ] as const
            ).map(([icon, value, label]) => (
              <div className="metric-card" key={label}>
                <span className={icon} aria-hidden="true" />
                <div>
                  <strong>{value}</strong>
                  <p>{label}</p>
                </div>
              </div>
            ))}
          </div>
          <p className="statistics-rule">
            Une ressource compte comme consultée dès sa première ouverture par
            l’élève. Seuls les élèves actuellement inscrits dans les groupes
            actifs associés au cours sont pris en compte.
          </p>
          <section className="panel">
            <div className="panel-heading">
              <h2>Consultation par ressource</h2>
              <button className="text-button" onClick={reload}>
                Actualiser les statistiques
              </button>
            </div>
            {data.resources.length ? (
              <div
                className="table-scroll course-table-scroll"
                role="region"
                aria-label="Consultation par ressource"
                tabIndex={0}
              >
                <table className="course-table">
                  <caption className="visually-hidden">
                    Consultation de chaque ressource du cours
                  </caption>
                  <thead>
                    <tr>
                      <th scope="col">Ressource</th>
                      <th scope="col">Chapitre</th>
                      <th scope="col">Type</th>
                      <th scope="col">Élèves ayant consulté</th>
                      <th scope="col">Taux</th>
                      <th scope="col">Consultations</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.resources.map((resource) => (
                      <tr key={resource.id}>
                        <th scope="row">{resource.title}</th>
                        <td>{resource.chapter_title}</td>
                        <td>{resourceKinds[resource.kind]}</td>
                        <td>
                          {resource.viewers} / {data.summary.students}
                        </td>
                        <td>{percent(resource.rate)}</td>
                        <td>{resource.total_views}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <Empty title="Aucune ressource">
                Importez des ressources dans le cours pour suivre leur
                consultation.
              </Empty>
            )}
          </section>
          <section className="panel">
            <h2>Progression des élèves</h2>
            {data.students.length ? (
              <div
                className="table-scroll course-table-scroll"
                role="region"
                aria-label="Progression des élèves"
                tabIndex={0}
              >
                <table className="course-table">
                  <caption className="visually-hidden">
                    Ressources consultées par chaque élève
                  </caption>
                  <thead>
                    <tr>
                      <th scope="col">Élève</th>
                      <th scope="col">Ressources consultées</th>
                      <th scope="col">Progression</th>
                      <th scope="col">Dernière consultation</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.students.map((student) => (
                      <tr key={student.id}>
                        <th scope="row">
                          {student.last_name} {student.first_name}
                        </th>
                        <td>
                          {student.viewed} / {student.total}
                        </td>
                        <td>{percent(student.percent)}</td>
                        <td>
                          {student.last_viewed_at
                            ? date(student.last_viewed_at)
                            : "Aucune consultation"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <Empty title="Aucun élève inscrit">
                Les élèves actuellement inscrits dans les groupes du cours
                apparaîtront ici.
              </Empty>
            )}
          </section>
        </>
      )}
    </div>
  );
}
