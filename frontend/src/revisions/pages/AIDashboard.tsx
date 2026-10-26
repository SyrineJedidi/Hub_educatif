import { useState } from "react";
import { Link } from "react-router-dom";
import { date } from "../../api/client";
import { useResource } from "../../hooks/useResource";
import { Alert, Loading } from "../../components/UI";
import type { AIJob, AIMetrics } from "../types";
import { engines, jobStatuses, percent, seconds } from "../types";
import { useSheetContext } from "../hooks/useSheetContext";
import "../styles/revisions.css";
import "../styles/dashboard.css";
const day = (iso: string) =>
  new Intl.DateTimeFormat("fr-FR", { day: "2-digit", month: "short" }).format(
    new Date(iso + "T12:00:00"),
  );
function Kpi({
  label,
  value,
  hint,
  icon,
}: {
  label: string;
  value: string;
  hint: string;
  icon: string;
}) {
  return (
    <div className="kpi">
      <dt>
        <span className={icon} aria-hidden="true" />
        {label}
      </dt>
      <dd className="kpi-value">{value}</dd>
      <dd className="kpi-hint">{hint}</dd>
    </div>
  );
}
function DailyChart({ rows }: { rows: AIMetrics["per_day"] }) {
  const [active, setActive] = useState<number | null>(null);
  const max = Math.max(1, ...rows.map((r) => r.count));
  const ticks =
    max <= 4
      ? Array.from({ length: max + 1 }, (_, i) => i)
      : [0, Math.round(max / 2), max];
  return (
    <figure className="chart" aria-labelledby="daily-title">
      <figcaption id="daily-title">
        Générations par jour (14 derniers jours)
      </figcaption>
      <div className="chart-plot" onMouseLeave={() => setActive(null)}>
        <div className="chart-grid" aria-hidden="true">
          {ticks
            .slice()
            .reverse()
            .map((t) => (
              <span key={t} style={{ bottom: (t / max) * 100 + "%" }}>
                {t}
              </span>
            ))}
        </div>
        <ol className="chart-bars">
          {rows.map((row, i) => (
            <li
              key={row.date}
              tabIndex={0}
              onMouseEnter={() => setActive(i)}
              onFocus={() => setActive(i)}
              onBlur={() => setActive(null)}
              aria-label={`${day(row.date)} : ${row.count} génération${row.count > 1 ? "s" : ""}`}
            >
              <span
                className="chart-bar"
                style={{ height: (row.count / max) * 100 + "%" }}
              />
              {active === i && (
                <span className="chart-tip" role="tooltip">
                  <strong>{row.count}</strong> génération
                  {row.count > 1 ? "s" : ""}
                  <small>{day(row.date)}</small>
                </span>
              )}
              <span className="chart-label" aria-hidden="true">
                {i % 2 === 1 ? "" : day(row.date)}
              </span>
            </li>
          ))}
        </ol>
      </div>
      <details className="chart-table">
        <summary>Voir les données</summary>
        <table>
          <thead>
            <tr>
              <th scope="col">Jour</th>
              <th scope="col">Générations</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.date}>
                <td>{day(r.date)}</td>
                <td>{r.count}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </details>
    </figure>
  );
}
function JobRow({ job, admin }: { job: AIJob; admin: boolean }) {
  const [label, icon] = jobStatuses[job.status];
  return (
    <tr>
      <td>{date(job.created_at)}</td>
      {admin && <td>{job.user_name}</td>}
      <td className="cell-title">{job.sheet_title}</td>
      <td>{job.kind === "SUMMARY" ? "Résumé" : "Illustration"}</td>
      <td>
        {job.engine ? engines[job.engine] || job.engine : "—"}
        {job.fallback && <small> (secours)</small>}
      </td>
      <td>
        <span className={"job-chip status-" + job.status.toLowerCase()}>
          <span className={icon} aria-hidden="true" /> {label}
        </span>
        {job.error && <small className="cell-error">{job.error}</small>}
      </td>
      <td className="num">{seconds(job.duration_ms)}</td>
      <td className="num">
        {job.kind === "SUMMARY" ? percent(job.metrics.keyword_coverage) : "—"}
      </td>
      <td className="num">{job.rating ? job.rating + " / 5" : "—"}</td>
    </tr>
  );
}
export default function AIDashboard() {
  const { admin, base } = useSheetContext();
  const [days, setDays] = useState(30);
  const { data, error, loading, reload } = useResource<AIMetrics>(
    "ai/metrics/?days=" + days,
  );
  const latencyMax = Math.max(
    1,
    ...(data?.latency.map((l) => l.p95_ms) || [1]),
  );
  const ratingMax = Math.max(1, ...(data?.rating.distribution || [1]));
  return (
    <div className="sheets-module ai-dashboard">
      <nav className="sheet-back" aria-label="Retour">
        <Link to={base}>
          <span className="ti-arrow-left" aria-hidden="true" /> Fiches de
          révision
        </Link>
      </nav>
      <header className="dash-heading">
        <div>
          <p className="eyebrow">
            RÉSUMÉS ET ILLUSTRATIONS · INTELLIGENCE ARTIFICIELLE
          </p>
          <h1>{admin ? "Pilotage de l’IA" : "Mes statistiques IA"}</h1>
          <p>
            Performance, qualité mesurée et adoption des générations Gemini,
            Ollama et Hugging Face
            {admin ? " sur toute la plateforme" : " pour vos fiches"}.
          </p>
        </div>
        <div className="dash-controls">
          <div className="sheets-segmented" role="group" aria-label="Période">
            {[7, 30, 90].map((value) => (
              <button
                key={value}
                type="button"
                aria-pressed={days === value}
                onClick={() => setDays(value)}
              >
                {value} jours
              </button>
            ))}
          </div>
          <button
            type="button"
            className="sheets-ghost-button"
            onClick={reload}
          >
            <span className="ti-reload" aria-hidden="true" /> Actualiser
          </button>
        </div>
      </header>
      <Alert error={error} />
      {loading && !data ? (
        <Loading />
      ) : data ? (
        <>
          <ul className="dash-config" aria-label="Configuration">
            <li>
              <span className="ti-server" aria-hidden="true" /> Traitement :{" "}
              <strong>
                {data.configuration.job_backend === "celery"
                  ? "Celery + Redis"
                  : data.configuration.job_backend === "thread"
                    ? "File de tâches intégrée"
                    : "Synchrone"}
              </strong>
            </li>
            <li>
              <span className="ti-book" aria-hidden="true" /> Résumés :{" "}
              <strong>{data.configuration.gemini_model || "—"}</strong>
            </li>
            <li>
              <span className="ti-shield" aria-hidden="true" /> Secours :{" "}
              <strong>{data.configuration.ollama_model || "aucun"}</strong>
            </li>
            <li>
              <span className="ti-image" aria-hidden="true" /> Images :{" "}
              <strong>{data.configuration.image_model || "—"}</strong>
            </li>
          </ul>
          <dl className="kpi-grid">
            <Kpi
              icon="ti-bolt"
              label="Générations"
              value={String(data.totals.jobs)}
              hint={`${data.totals.summaries} résumés · ${data.totals.illustrations} illustrations`}
            />
            <Kpi
              icon="ti-check-box"
              label="Taux de réussite"
              value={percent(data.success_rate)}
              hint={`${data.totals.succeeded} réussies · ${data.totals.failed} en échec`}
            />
            <Kpi
              icon="ti-timer"
              label="Attente en file"
              value={seconds(data.queue_mean_ms)}
              hint="Délai moyen avant prise en charge par le worker"
            />
            <Kpi
              icon="ti-target"
              label="Couverture des mots-clés"
              value={percent(data.quality.keyword_coverage)}
              hint="Notions clés du cours retrouvées dans la fiche"
            />
            <Kpi
              icon="ti-layout-grid2"
              label="Conformité de structure"
              value={percent(data.quality.structure_score)}
              hint="Sections, points clés, glossaire, longueur"
            />
            <Kpi
              icon="ti-star"
              label="Pertinence (utilisateurs)"
              value={
                data.rating.mean
                  ? data.rating.mean.toLocaleString("fr-FR", {
                      maximumFractionDigits: 1,
                    }) + " / 5"
                  : "—"
              }
              hint={`${data.rating.count} note${data.rating.count > 1 ? "s" : ""}`}
            />
            <Kpi
              icon="ti-eye"
              label="Contenus relus"
              value={percent(data.review_rate)}
              hint="Fiches générées validées par leur auteur"
            />
            <Kpi
              icon="ti-shield"
              label="Recours au secours"
              value={percent(data.fallback_rate)}
              hint="Résumés rédigés par Ollama (Gemini indisponible)"
            />
          </dl>
          <div className="dash-grid">
            <section className="dash-card wide">
              <DailyChart rows={data.per_day} />
            </section>
            <section className="dash-card" aria-labelledby="latency-title">
              <h2 id="latency-title">Temps de génération par moteur</h2>
              {data.latency.length ? (
                <div
                  className="table-scroll"
                  tabIndex={0}
                  role="region"
                  aria-labelledby="latency-title"
                >
                  <table className="latency">
                    <thead>
                      <tr>
                        <th scope="col">Moteur</th>
                        <th scope="col" className="num">
                          n
                        </th>
                        <th scope="col">Médiane (p50)</th>
                        <th scope="col" className="num">
                          p95
                        </th>
                      </tr>
                    </thead>
                    <tbody>
                      {data.latency.map((l) => (
                        <tr key={l.engine}>
                          <th scope="row">{engines[l.engine] || l.engine}</th>
                          <td className="num">{l.count}</td>
                          <td>
                            <span className="inline-bar">
                              <span
                                style={{
                                  width: (l.p50_ms / latencyMax) * 100 + "%",
                                }}
                              />
                            </span>
                            {seconds(l.p50_ms)}
                          </td>
                          <td className="num">{seconds(l.p95_ms)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <p className="field-help">
                  Aucune génération terminée sur la période.
                </p>
              )}
              <p className="dash-note">
                La requête HTTP répond immédiatement (202) : ces durées
                s’écoulent en arrière-plan.
              </p>
            </section>
            <section className="dash-card" aria-labelledby="rating-title">
              <h2 id="rating-title">Notes de pertinence</h2>
              <ol className="rating-bars">
                {data.rating.distribution
                  .map((count, i) => ({ count, stars: i + 1 }))
                  .reverse()
                  .map(({ count, stars }) => (
                    <li key={stars}>
                      <span className="rating-label">{stars} ★</span>
                      <span className="inline-bar">
                        <span
                          style={{ width: (count / ratingMax) * 100 + "%" }}
                        />
                      </span>
                      <span className="num">{count}</span>
                    </li>
                  ))}
              </ol>
              <p className="dash-note">
                Note de 1 à 5 donnée par l’auteur après chaque résumé.
              </p>
            </section>
            <section className="dash-card" aria-labelledby="quality-title">
              <h2 id="quality-title">Qualité mesurée des résumés</h2>
              <dl className="quality-list">
                <div>
                  <dt>Couverture des mots-clés</dt>
                  <dd>{percent(data.quality.keyword_coverage)}</dd>
                  <dd className="quality-help">
                    Part des 15 termes les plus fréquents du cours présents dans
                    le résumé, les points clés ou le glossaire.
                  </dd>
                </div>
                <div>
                  <dt>Taux de compression</dt>
                  <dd>
                    {data.quality.compression == null
                      ? "—"
                      : percent(data.quality.compression)}
                  </dd>
                  <dd className="quality-help">
                    Longueur du résumé rapportée à celle du cours : il doit
                    condenser, pas recopier.
                  </dd>
                </div>
                <div>
                  <dt>Conformité de structure</dt>
                  <dd>{percent(data.quality.structure_score)}</dd>
                  <dd className="quality-help">
                    Sections titrées, nombre de points clés, glossaire, longueur
                    demandée, idée d’illustration.
                  </dd>
                </div>
              </dl>
            </section>
            <section className="dash-card" aria-labelledby="errors-title">
              <h2 id="errors-title">Erreurs principales</h2>
              {data.errors.length ? (
                <ul className="error-list">
                  {data.errors.map(([message, count]) => (
                    <li key={message}>
                      <span className="num">{count}×</span> {message}
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="dash-empty">
                  <span className="ti-check" aria-hidden="true" /> Aucune erreur
                  sur la période.
                </p>
              )}
            </section>
          </div>
          <section className="dash-card" aria-labelledby="recent-title">
            <h2 id="recent-title">Dernières générations</h2>
            {data.recent.length ? (
              <div
                className="table-scroll"
                tabIndex={0}
                role="region"
                aria-labelledby="recent-title"
              >
                <table className="jobs-table">
                  <thead>
                    <tr>
                      <th scope="col">Date</th>
                      {admin && <th scope="col">Utilisateur</th>}
                      <th scope="col">Fiche</th>
                      <th scope="col">Type</th>
                      <th scope="col">Moteur</th>
                      <th scope="col">Statut</th>
                      <th scope="col" className="num">
                        Durée
                      </th>
                      <th scope="col" className="num">
                        Couverture
                      </th>
                      <th scope="col" className="num">
                        Note
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.recent.map((job) => (
                      <JobRow key={job.id} job={job} admin={admin} />
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <p className="field-help">Aucune génération pour le moment.</p>
            )}
          </section>
        </>
      ) : null}
    </div>
  );
}
