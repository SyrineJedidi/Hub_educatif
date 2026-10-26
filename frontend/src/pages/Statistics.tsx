import { useEffect, useState } from "react";
import { useAuth } from "../auth/AuthContext";
import { allPages, date, iso, query } from "../api/client";
import type { Stats, Group, Summary } from "../api/types";
import { useResource } from "../hooks/useResource";
import {
  Alert,
  Field,
  Select,
  Loading,
  Empty,
  Pagination,
  Badge,
  statuses,
} from "../components/UI";
export default function Statistics() {
  const { user } = useAuth();
  const [group, setGroup] = useState(""),
    [from, setFrom] = useState(""),
    [to, setTo] = useState(""),
    [page, setPage] = useState(1),
    [groups, setGroups] = useState<Group[]>([]),
    [groupError, setGroupError] = useState<unknown>();
  useEffect(() => {
    allPages<Group>("groups/").then(setGroups).catch(setGroupError);
  }, []);
  const params = query({
    group,
    from: from ? iso(from + "T00:00") : "",
    to: to ? iso(to + "T00:00") : "",
    page,
  });
  const { data, error, loading } = useResource<Stats>("statistics/?" + params);
  return (
    <>
      <div className="page-heading">
        <div>
          <p className="eyebrow">COMPRENDRE SON PARCOURS</p>
          <h1>
            {user!.role === "STUDENT"
              ? "Mon assiduité"
              : "Assiduité et statistiques"}
          </h1>
          <p>
            Une vision claire des présences, fondée sur les feuilles validées.
          </p>
        </div>
        {user!.role !== "STUDENT" && (
          <a className="btn_one" href={"/api/statistics/export/?" + params}>
            Exporter en CSV ↓
          </a>
        )}
      </div>
      <section className="panel">
        <div className="filters">
          <Select
            label="Groupe"
            value={group}
            onChange={(e) => {
              setGroup(e.target.value);
              setPage(1);
            }}
          >
            <option value="">Tous mes groupes</option>
            {groups.map((g) => (
              <option key={g.id} value={g.id}>
                {g.name}
              </option>
            ))}
          </Select>
          <Field
            label="À partir du"
            type="date"
            value={from}
            onChange={(e) => {
              setFrom(e.target.value);
              setPage(1);
            }}
          />
          <Field
            label="Avant le"
            type="date"
            value={to}
            onChange={(e) => {
              setTo(e.target.value);
              setPage(1);
            }}
          />
        </div>
        <Alert error={error || groupError} />
        {loading ? (
          <Loading />
        ) : (
          data && (
            <>
              <div className="metric-grid">
                <div className="metric-card">
                  <div>
                    <strong>
                      {data.rate === null ? "Non calculable" : data.rate + " %"}
                    </strong>
                    <p>Taux de présence</p>
                  </div>
                </div>
                {Object.entries(data.totals).map(([s, v]) => (
                  <div key={s} className="metric-card">
                    <div>
                      <strong>{v}</strong>
                      <p>{statuses[s]}</p>
                    </div>
                  </div>
                ))}
              </div>
              <p className="statistics-rule">
                Convention du projet Nexora : (présences + retards) / (présences
                + retards + absences non justifiées) × 100. Les absences
                justifiées sont présentées séparément. Seules les feuilles
                validées des séances terminées dans le temps et non annulées
                sont retenues. Ce calcul n’est pas un règlement officiel
                d’ESPRIT.
              </p>
              <h2>Historique de l’assiduité</h2>
              {data.results.length ? (
                <>
                  <div
                    className="table-scroll"
                    tabIndex={0}
                    role="region"
                    aria-label="Historique de l’assiduité"
                  >
                    <table>
                      <thead>
                        <tr>
                          <th>Séance</th>
                          <th>Date</th>
                          {user!.role !== "STUDENT" && <th>Étudiant</th>}
                          <th>Statut</th>
                        </tr>
                      </thead>
                      <tbody>
                        {data.results.map((r) => (
                          <tr key={r.session_id + r.student_id}>
                            <td>
                              {r.session_title}
                              <small>{r.group_name}</small>
                            </td>
                            <td>{date(r.starts_at)}</td>
                            {user!.role !== "STUDENT" && (
                              <td>{r.student_name}</td>
                            )}
                            <td>
                              <Badge>{statuses[r.status]}</Badge>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                  <Pagination
                    count={data.count}
                    page={page}
                    onChange={setPage}
                  />
                </>
              ) : (
                <Empty>
                  Aucune feuille exploitable pour la période choisie. Le taux
                  n’est pas encore calculable.
                </Empty>
              )}
              {user!.role !== "STUDENT" && data.by_student.length > 0 && (
                <div className="dashboard-columns">
                  <SummaryTable label="Par étudiant" rows={data.by_student} />
                  <SummaryTable label="Par séance" rows={data.by_session} />
                </div>
              )}
            </>
          )
        )}
      </section>
    </>
  );
}
function SummaryTable({ label, rows }: { label: string; rows: Summary[] }) {
  return (
    <div>
      <h2>{label}</h2>
      <div
        className="table-scroll"
        tabIndex={0}
        role="region"
        aria-label={"Synthèse " + label}
      >
        <table>
          <thead>
            <tr>
              <th>Nom</th>
              <th>Présences</th>
              <th>Retards</th>
              <th>Absences</th>
              <th>Justifiées</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.id}>
                <td>{r.label}</td>
                <td>{r.PRESENT}</td>
                <td>{r.LATE}</td>
                <td>{r.ABSENT}</td>
                <td>{r.EXCUSED}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
