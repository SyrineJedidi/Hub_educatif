import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { date, query } from "../../api/client";
import { useResource } from "../../hooks/useResource";
import type { Page } from "../../api/types";
import { Alert, Loading, Pagination } from "../../components/UI";
import type { AIJob } from "../types";
import { engines, illustrationStyles, jobStatuses, percent, seconds, summaryLengths } from "../types";
import { useSheetContext } from "../hooks/useSheetContext";
import "../styles/backoffice.css";
export function JobStatusPill({ job }: { job: AIJob }) {
  const [label, icon] = jobStatuses[job.status];
  return (
    <span className={"bo-pill job-" + job.status.toLowerCase()}>
      <span className={icon} aria-hidden="true" /> {label}
    </span>
  );
}
export function jobLabel(job: AIJob) {
  return job.kind === "SUMMARY"
    ? "Résumé · " + summaryLengths[job.params.length || "STANDARD"][0]
    : "Illustration · " + illustrationStyles[job.params.style || "SCHEMA"][0];
}
/** Journal of every AI generation, with its engine, duration and measured quality. */
export default function JobJournal() {
  const { admin, base, paths } = useSheetContext();
  const [kind, setKind] = useState(""),
    [status, setStatus] = useState(""),
    [page, setPage] = useState(1);
  const { data, error, loading, reload } = useResource<Page<AIJob>>(
    "ai/jobs/?" + query({ kind, status, page }),
  );
  const running = data?.results.some((j) => j.status === "QUEUED" || j.status === "RUNNING");
  // Running generations are refreshed until they finish.
  useEffect(() => {
    if (!running) return;
    const timer = window.setTimeout(reload, 2000);
    return () => window.clearTimeout(timer);
  }, [running, data]);
  return (
    <div className="bo-page">
      <header className="bo-page-head">
        <div>
          <p className="bo-eyebrow">Résumés et illustrations · Intelligence artificielle</p>
          <h1>Journal des générations</h1>
          <p>
            Chaque appel à l’IA est tracé : moteur utilisé, temps d’attente et de
            calcul, qualité mesurée, note donnée{admin ? " et auteur" : ""}.
          </p>
        </div>
        <div className="bo-head-actions">
          <Link className="bo-btn" to={paths.stats}>
            <span className="ti-pulse" aria-hidden="true" /> {admin ? "Pilotage de l’IA" : "Statistiques IA"}
          </Link>
          <Link className="bo-btn bo-btn-ai" to={paths.workshop}>
            <span className="ti-wand" aria-hidden="true" /> Atelier IA
          </Link>
        </div>
      </header>
      <section className="bo-card" aria-label="Générations">
        <div className="bo-toolbar">
          <label className="bo-filter">
            <span>Type</span>
            <select value={kind} onChange={(e) => { setKind(e.target.value); setPage(1); }}>
              <option value="">Tous</option>
              <option value="SUMMARY">Résumés</option>
              <option value="ILLUSTRATION">Illustrations</option>
            </select>
          </label>
          <label className="bo-filter">
            <span>Statut</span>
            <select value={status} onChange={(e) => { setStatus(e.target.value); setPage(1); }}>
              <option value="">Tous</option>
              {Object.entries(jobStatuses).map(([key, [label]]) => (
                <option key={key} value={key}>{label}</option>
              ))}
            </select>
          </label>
        </div>
        <Alert error={error} />
        {loading && !data ? (
          <Loading />
        ) : data?.results.length ? (
          <div className="bo-table-wrap">
            <table className="bo-table">
              <caption className="sr-only">Journal des générations IA</caption>
              <thead>
                <tr>
                  <th scope="col">Génération</th>
                  <th scope="col">Fiche</th>
                  {admin && <th scope="col">Auteur</th>}
                  <th scope="col">Statut</th>
                  <th scope="col">Moteur</th>
                  <th scope="col" className="bo-num">Attente</th>
                  <th scope="col" className="bo-num">Calcul</th>
                  <th scope="col" className="bo-num">Mots-clés</th>
                  <th scope="col" className="bo-num">Note</th>
                </tr>
              </thead>
              <tbody>
                {data.results.map((job) => (
                  <tr key={job.id}>
                    <td data-label="Génération" className="bo-cell-main">
                      <strong className="bo-row-strong">{jobLabel(job)}</strong>
                      <small>{date(job.created_at)}</small>
                    </td>
                    <td data-label="Fiche">
                      {job.sheet_id ? <Link to={base + "/" + job.sheet_id}>{job.sheet_title}</Link> : <span className="bo-muted">{job.sheet_title} (supprimée)</span>}
                    </td>
                    {admin && <td data-label="Auteur">{job.user_name}</td>}
                    <td data-label="Statut">
                      <JobStatusPill job={job} />
                      {job.status === "FAILED" && <small className="bo-error-text">{job.error}</small>}
                    </td>
                    <td data-label="Moteur">
                      {job.engine ? (engines[job.engine] || job.engine) : "—"}
                      {job.fallback && <small>Secours local</small>}
                    </td>
                    <td data-label="Attente" className="bo-num">{seconds(job.queue_ms)}</td>
                    <td data-label="Calcul" className="bo-num">{seconds(job.duration_ms)}</td>
                    <td data-label="Mots-clés" className="bo-num">
                      {job.kind === "SUMMARY" ? percent(job.metrics.keyword_coverage) : "—"}
                    </td>
                    <td data-label="Note" className="bo-num">
                      {job.rating ? job.rating + " / 5" : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="bo-empty">
            <span className="ti-list" aria-hidden="true" />
            <h2>Aucune génération</h2>
            <p>Lancez une première génération depuis l’atelier IA.</p>
          </div>
        )}
        {data && (
          <div className="bo-table-foot">
            <span>{data.count} génération{data.count > 1 ? "s" : ""}</span>
            <Pagination page={page} count={data.count} onChange={setPage} />
          </div>
        )}
      </section>
    </div>
  );
}
