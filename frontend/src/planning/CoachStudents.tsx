import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { allPages, date, query } from "../api/client";
import type { Group, Page } from "../api/types";
import { useResource } from "../hooks/useResource";
import {
  Alert,
  Empty,
  Field,
  Loading,
  Pagination,
  Select,
} from "../components/UI";
import { usePlanningContext } from "./usePlanningContext";
import { LoadFailure } from "./PlanningWidgets";
import { fullName, percent, period, plural } from "./format";
import type { CoachStudent } from "./types";
import "./planning.css";
export default function CoachStudents() {
  const { admin, coachApi, coachBase } = usePlanningContext();
  const [q, setQ] = useState(""),
    [group, setGroup] = useState(""),
    [page, setPage] = useState(1);
  const [groups, setGroups] = useState<Group[]>([]),
    [groupError, setGroupError] = useState<unknown>();
  useEffect(() => {
    let active = true;
    // Archived groups are outside the coaching scope.
    allPages<Group>("groups/?archived=false")
      .then((items) => {
        if (active) setGroups(items);
      })
      .catch((error) => {
        if (active) setGroupError(error);
      });
    return () => {
      active = false;
    };
  }, []);
  const { data, error, loading, reload } = useResource<Page<CoachStudent>>(
    coachApi + "?" + query({ group, q: q.trim(), page }),
  );
  const filtered = !!(group || q.trim());
  function reset() {
    setQ("");
    setGroup("");
    setPage(1);
  }
  return (
    <div className="planning-module">
      <div className="page-heading">
        <div>
          <p className="eyebrow">PLANIFICATION ET COACHING</p>
          <h1>Suivi des révisions</h1>
          <p>
            {admin
              ? "Consultez l’avancement des plannings de révision de tous les élèves."
              : "Consultez l’avancement des plannings de révision des élèves de vos groupes actifs."}{" "}
            Ce suivi est en lecture seule.
          </p>
        </div>
      </div>
      <section
        className="panel planning-filters"
        aria-label="Rechercher et filtrer les élèves"
      >
        <div className="filters">
          <Field
            label="Rechercher un élève"
            type="search"
            placeholder="Nom ou prénom"
            maxLength={100}
            value={q}
            onChange={(e) => {
              setQ(e.target.value);
              setPage(1);
            }}
          />
          <Select
            label="Groupe"
            value={group}
            onChange={(e) => {
              setGroup(e.target.value);
              setPage(1);
            }}
          >
            <option value="">
              {admin ? "Tous les groupes" : "Tous mes groupes"}
            </option>
            {groups.map((item) => (
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
        <Alert error={groupError} />
      </section>
      {loading && !data ? (
        <Loading />
      ) : !data ? (
        <LoadFailure error={error} onRetry={reload} />
      ) : (
        <section className="panel" aria-labelledby="planning-students-title">
          <div className="panel-heading">
            <h2 id="planning-students-title">
              {plural(data.count, "élève", "élèves")}
            </h2>
            <button className="text-button" onClick={reload}>
              Actualiser
            </button>
          </div>
          <Alert error={error} />
          {data.results.length ? (
            <>
              <div
                className="table-scroll"
                role="region"
                aria-label="Avancement des élèves"
                tabIndex={0}
              >
                <table className="planning-table planning-coach-table">
                  <caption className="visually-hidden">
                    Avancement des plannings de révision par élève
                  </caption>
                  <thead>
                    <tr>
                      <th scope="col">Élève</th>
                      <th scope="col">Groupes</th>
                      <th scope="col">Planning actif</th>
                      <th scope="col">Taux de réalisation</th>
                      <th scope="col">En retard</th>
                      <th scope="col">Dernière activité</th>
                      <th scope="col">Prochaine échéance</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.results.map((row) => (
                      <tr key={row.student.id}>
                        <th scope="row">
                          <Link to={coachBase + "/" + row.student.id}>
                            {fullName(row.student) || "Élève"}
                          </Link>
                        </th>
                        <td>
                          {row.groups.length
                            ? row.groups.map((item) => item.name).join(", ")
                            : "Aucun groupe"}
                        </td>
                        <td>
                          {row.active_plan ? (
                            <>
                              {row.active_plan.title}
                              <small>
                                {period(
                                  row.active_plan.start_date,
                                  row.active_plan.end_date,
                                )}
                              </small>
                            </>
                          ) : (
                            "Aucun planning actif"
                          )}
                        </td>
                        <td>
                          {percent(row.progress.completion_rate)}
                          <small>
                            {plural(
                              row.progress.done,
                              "tâche terminée",
                              "tâches terminées",
                            )}
                          </small>
                        </td>
                        <td>{row.progress.overdue}</td>
                        <td>
                          {row.last_done_at
                            ? date(row.last_done_at)
                            : "Aucune tâche terminée"}
                        </td>
                        <td>
                          {row.next_deadline ? (
                            <>
                              {row.next_deadline.title}
                              <small>{date(row.next_deadline.due_at)}</small>
                            </>
                          ) : (
                            "Aucune"
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <Pagination page={page} count={data.count} onChange={setPage} />
            </>
          ) : (
            <>
              <Empty
                title={filtered ? "Aucun résultat" : "Aucun élève à suivre"}
              >
                {filtered
                  ? "Aucun élève ne correspond à ces critères. Essayez une autre recherche ou réinitialisez les filtres."
                  : admin
                    ? "Aucun élève n’est inscrit pour le moment."
                    : "Aucun élève n’est actuellement inscrit dans vos groupes actifs."}
              </Empty>
              {filtered && (
                <p className="planning-center">
                  <button className="btn_one" onClick={reset}>
                    Afficher tous les élèves
                  </button>
                </p>
              )}
            </>
          )}
        </section>
      )}
    </div>
  );
}
