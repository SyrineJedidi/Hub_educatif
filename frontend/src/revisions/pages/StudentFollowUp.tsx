import { useState } from "react";
import { Link } from "react-router-dom";
import { date } from "../../api/client";
import { useResource } from "../../hooks/useResource";
import { Alert, Loading } from "../../components/UI";
import { percent } from "../types";
import { useSheetContext } from "../hooks/useSheetContext";
import "../styles/backoffice.css";
interface StudentRow {
  student_id: string;
  name: string;
  views: number;
  last_viewed_at: string | null;
  review_sessions: number;
  mastery: number | null;
}
interface SheetRow {
  sheet_id: string;
  title: string;
  course_label: string;
  group_name: string;
  published_at: string | null;
  students: number;
  readers: number;
  cards: number;
  average_mastery: number | null;
  last_viewed_at: string | null;
  details: StudentRow[];
}
function Meter({ value, label }: { value: number | null; label: string }) {
  return (
    <span className="fu-meter">
      <span className="fu-meter-track" aria-hidden="true">
        <span style={{ width: Math.round((value || 0) * 100) + "%" }} />
      </span>
      <span>{value == null ? "—" : percent(value)}</span>
      <span className="sr-only">{label}</span>
    </span>
  );
}
/** Teacher follow-up: who read and revised each published sheet, and how well. */
export default function StudentFollowUp() {
  const { base, admin } = useSheetContext();
  const { data, error, loading } = useResource<{ results: SheetRow[] }>("revisions/engagement/");
  const [open, setOpen] = useState<string | null>(null);
  const rows = data?.results || [];
  const students = rows.reduce((n, r) => n + r.students, 0);
  const readers = rows.reduce((n, r) => n + r.readers, 0);
  const masteries = rows.map((r) => r.average_mastery).filter((m): m is number => m != null);
  return (
    <div className="bo-page">
      <header className="bo-page-head">
        <div>
          <p className="bo-eyebrow">Résumés et illustrations · Suivi pédagogique</p>
          <h1>Suivi des étudiants</h1>
          <p>
            Pour chaque fiche publiée{admin ? "" : " dans vos groupes"} : qui l’a
            lue, qui l’a révisée avec les cartes mémoire et quel niveau de
            maîtrise est atteint. Repérez les étudiants à relancer.
          </p>
        </div>
      </header>
      <dl className="bo-kpis fu-kpis">
        <div className="bo-kpi">
          <span className="ti-share" aria-hidden="true" />
          <dt>Fiches publiées suivies</dt>
          <dd>{rows.length}</dd>
        </div>
        <div className="bo-kpi good">
          <span className="ti-eye" aria-hidden="true" />
          <dt>Taux de lecture</dt>
          <dd>{percent(students ? readers / students : null)}</dd>
        </div>
        <div className="bo-kpi ai">
          <span className="ti-layers-alt" aria-hidden="true" />
          <dt>Maîtrise moyenne</dt>
          <dd>{percent(masteries.length ? masteries.reduce((a, b) => a + b, 0) / masteries.length : null)}</dd>
        </div>
      </dl>
      <Alert error={error} />
      <section className="bo-card" aria-label="Lecture et maîtrise par fiche">
        {loading && !data ? (
          <Loading />
        ) : rows.length ? (
          <ul className="fu-list">
            {rows.map((row) => {
              const expanded = open === row.sheet_id;
              return (
                <li key={row.sheet_id}>
                  <div className="fu-row">
                    <div className="fu-main">
                      <Link className="bo-row-title" to={base + "/" + row.sheet_id}>
                        {row.title}
                      </Link>
                      <small>
                        {row.group_name} · {row.cards} carte{row.cards > 1 ? "s" : ""} de révision
                        {row.published_at && " · publiée le " + date(row.published_at)}
                      </small>
                    </div>
                    <div className="fu-figure">
                      <small>Lecteurs</small>
                      <strong>
                        {row.readers} / {row.students}
                      </strong>
                    </div>
                    <div className="fu-figure fu-wide">
                      <small>Maîtrise moyenne</small>
                      <Meter value={row.average_mastery} label={"Maîtrise moyenne de " + row.title} />
                    </div>
                    <div className="fu-figure">
                      <small>Dernière lecture</small>
                      <strong className="fu-date">{row.last_viewed_at ? date(row.last_viewed_at) : "—"}</strong>
                    </div>
                    <button
                      type="button"
                      className="bo-btn bo-btn-small"
                      aria-expanded={expanded}
                      aria-controls={"fu-" + row.sheet_id}
                      onClick={() => setOpen(expanded ? null : row.sheet_id)}
                    >
                      {expanded ? "Masquer" : "Détail par étudiant"}
                      <span className={expanded ? "ti-angle-up" : "ti-angle-down"} aria-hidden="true" />
                    </button>
                  </div>
                  {expanded && (
                    <div id={"fu-" + row.sheet_id} className="bo-table-wrap fu-detail">
                      <table className="bo-table">
                        <caption className="sr-only">Détail par étudiant pour « {row.title} »</caption>
                        <thead>
                          <tr>
                            <th scope="col">Étudiant</th>
                            <th scope="col" className="bo-num">Lectures</th>
                            <th scope="col">Dernière lecture</th>
                            <th scope="col" className="bo-num">Révisions</th>
                            <th scope="col">Maîtrise</th>
                            <th scope="col">Situation</th>
                          </tr>
                        </thead>
                        <tbody>
                          {row.details.map((s) => (
                            <tr key={s.student_id}>
                              <td data-label="Étudiant" className="bo-cell-main">
                                <strong className="bo-row-strong">{s.name}</strong>
                              </td>
                              <td data-label="Lectures" className="bo-num">{s.views}</td>
                              <td data-label="Dernière lecture">{s.last_viewed_at ? date(s.last_viewed_at) : "—"}</td>
                              <td data-label="Révisions" className="bo-num">{s.review_sessions}</td>
                              <td data-label="Maîtrise">
                                <Meter value={s.mastery} label={"Maîtrise de " + s.name} />
                              </td>
                              <td data-label="Situation">
                                {!s.views && !s.review_sessions ? (
                                  <span className="bo-pill job-failed">Pas encore lue</span>
                                ) : (s.mastery ?? 0) >= 0.8 ? (
                                  <span className="bo-pill status-published">Maîtrisée</span>
                                ) : s.review_sessions ? (
                                  <span className="bo-pill status-draft">En progression</span>
                                ) : (
                                  <span className="bo-pill job-queued">Lue, pas révisée</span>
                                )}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                      {!row.details.length && <p className="bo-muted bo-pad">Aucun étudiant inscrit actuellement dans ce groupe.</p>}
                    </div>
                  )}
                </li>
              );
            })}
          </ul>
        ) : (
          <div className="bo-empty">
            <span className="ti-stats-up" aria-hidden="true" />
            <h2>Aucune fiche publiée</h2>
            <p>Le suivi apparaît dès qu’une fiche est publiée pour un groupe.</p>
          </div>
        )}
      </section>
    </div>
  );
}
