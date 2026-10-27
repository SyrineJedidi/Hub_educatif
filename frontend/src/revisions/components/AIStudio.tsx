import { useEffect, useId, useState } from "react";
import { api } from "../../api/client";
import "../styles/studio.css";
import { Alert, Modal } from "../../components/UI";
import type { AIJob, AIStatus } from "../types";
import {
  engines,
  illustrationStyles,
  jobStatuses,
  percent,
  seconds,
  summaryLengths,
} from "../types";
import { isActive } from "../hooks/useSheetJobs";
let statusCache: Promise<AIStatus> | null = null;
export function useAIStatus() {
  const [status, setStatus] = useState<AIStatus | null>(null);
  useEffect(() => {
    statusCache ??= api<AIStatus>("ai/status/");
    statusCache.then(setStatus).catch(() => {
      statusCache = null;
    });
  }, []);
  return status;
}
export function useElapsed(job: AIJob) {
  const [now, setNow] = useState(Date.now());
  const active = isActive(job);
  useEffect(() => {
    if (!active) return;
    const timer = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, [active]);
  return active
    ? Math.max(0, now - new Date(job.created_at).getTime())
    : job.duration_ms;
}
export function StudioButton({
  running,
  onClick,
}: {
  running: number;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      className={"ai-fab no-print" + (running ? " is-running" : "")}
      onClick={onClick}
      aria-label={
        "Ouvrir le Studio IA" +
        (running
          ? ` (${running} génération${running > 1 ? "s" : ""} en cours)`
          : "")
      }
    >
      <span className="ai-fab-icon" aria-hidden="true">
        <span className="ti-wand" />
      </span>
      <span className="ai-fab-label">Studio IA</span>
      {running > 0 && (
        <span className="ai-fab-count" aria-hidden="true">
          {running}
        </span>
      )}
    </button>
  );
}
export function RatingStars({
  job,
  onRated,
}: {
  job: AIJob;
  onRated: (job: AIJob) => void;
}) {
  const name = useId();
  const [error, setError] = useState<unknown>(),
    [busy, setBusy] = useState(false);
  async function rate(value: number) {
    setBusy(true);
    setError(undefined);
    try {
      onRated(
        await api<AIJob>("ai/jobs/" + job.id + "/rating/", "POST", {
          rating: value,
        }),
      );
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  }
  return (
    <fieldset className="ai-rating" disabled={busy}>
      <legend>
        {job.rating
          ? "Votre note de pertinence"
          : "Ce résumé est-il pertinent ?"}
      </legend>
      <div className="ai-rating-stars">
        {[1, 2, 3, 4, 5].map((value) => (
          <label key={value} title={value + " sur 5"}>
            <input
              type="radio"
              name={name}
              value={value}
              checked={job.rating === value}
              onChange={() => void rate(value)}
            />
            <span
              className={
                "ai-star" + (job.rating && value <= job.rating ? " is-on" : "")
              }
              aria-hidden="true"
            >
              ★
            </span>
            <span className="sr-only">
              {value} étoile{value > 1 ? "s" : ""} sur 5
            </span>
          </label>
        ))}
      </div>
      <Alert error={error} />
    </fieldset>
  );
}
export function JobItem({
  job,
  canRate,
  onRated,
}: {
  job: AIJob;
  canRate: boolean;
  onRated: (job: AIJob) => void;
}) {
  const elapsed = useElapsed(job);
  const [label, icon] = jobStatuses[job.status];
  const summary = job.kind === "SUMMARY";
  return (
    <li className={"ai-job status-" + job.status.toLowerCase()}>
      <div className="ai-job-head">
        <span className="ai-job-kind" aria-hidden="true">
          <span className={summary ? "ti-book" : "ti-image"} />
        </span>
        <div>
          <strong>
            {summary
              ? "Résumé · " + summaryLengths[job.params.length || "STANDARD"][0]
              : "Illustration · " +
                illustrationStyles[job.params.style || "SCHEMA"][0]}
          </strong>
          <small>
            {new Date(job.created_at).toLocaleTimeString("fr-FR", {
              hour: "2-digit",
              minute: "2-digit",
            })}
            {job.user_name && " · " + job.user_name}
            {job.engine &&
              " · " +
                (engines[job.engine] || job.engine) +
                " " +
                job.model.split("/").pop()}
          </small>
        </div>
        <span className="ai-job-status">
          <span className={icon} aria-hidden="true" /> {label}
        </span>
      </div>
      {isActive(job) ? (
        <div className="ai-job-progress" role="status">
          <span className="ai-job-bar" aria-hidden="true" />
          <span>
            {job.status === "QUEUED" ? "Dans la file d’attente" : "Génération"}{" "}
            depuis {seconds(elapsed)}
          </span>
        </div>
      ) : job.status === "FAILED" ? (
        <p className="ai-job-error">{job.error}</p>
      ) : (
        <>
          <dl className="ai-job-facts">
            <div>
              <dt>Durée</dt>
              <dd>{seconds(job.duration_ms)}</dd>
            </div>
            {summary ? (
              <>
                <div>
                  <dt>Mots-clés couverts</dt>
                  <dd>{percent(job.metrics.keyword_coverage)}</dd>
                </div>
                <div>
                  <dt>Structure</dt>
                  <dd>{percent(job.metrics.structure_score)}</dd>
                </div>
              </>
            ) : (
              <div>
                <dt>Attente</dt>
                <dd>{seconds(job.queue_ms)}</dd>
              </div>
            )}
          </dl>
          {job.fallback && (
            <p className="ai-job-note">
              <span className="ti-info-alt" aria-hidden="true" /> Gemini
              indisponible : rédigé par le modèle local.
            </p>
          )}
          {summary && canRate && <RatingStars job={job} onRated={onRated} />}
        </>
      )}
    </li>
  );
}
export function StudioDrawer({
  jobs,
  canSummarize,
  canIllustrate,
  blockedReason,
  canRate,
  onClose,
  onSummarize,
  onIllustrate,
  onRated,
}: {
  jobs: AIJob[];
  canSummarize: boolean;
  canIllustrate: boolean;
  blockedReason?: string;
  canRate: boolean;
  onClose: () => void;
  onSummarize: () => void;
  onIllustrate: () => void;
  onRated: (job: AIJob) => void;
}) {
  const status = useAIStatus();
  return (
    <Modal title="Studio IA" onClose={onClose}>
      <div className="sheets-module ai-studio">
        <p className="ai-studio-intro">
          Les générations tournent en arrière-plan : vous pouvez fermer ce
          panneau et continuer à travailler, la fiche se met à jour toute seule.
        </p>
        {status && (
          <ul
            className="ai-engines"
            aria-label="Moteurs d’intelligence artificielle"
          >
            <li className={status.summary ? "on" : "off"}>
              <span className="ti-book" aria-hidden="true" />
              {status.summary_engine || "Résumés non configurés"}
            </li>
            {status.fallback_engine && (
              <li className="on">
                <span className="ti-shield" aria-hidden="true" />
                Secours {status.fallback_engine}
              </li>
            )}
            <li className={status.illustration ? "on" : "off"}>
              <span className="ti-image" aria-hidden="true" />
              {status.illustration_engine || "Illustrations non configurées"}
            </li>
            <li className="on">
              <span className="ti-server" aria-hidden="true" />
              {status.job_backend}
            </li>
          </ul>
        )}
        <div className="ai-actions">
          <button
            type="button"
            className="ai-action summary"
            disabled={!canSummarize || status?.summary === false}
            onClick={onSummarize}
          >
            <span className="ai-action-icon" aria-hidden="true">
              <span className="ti-book" />
            </span>
            <strong>Résumer un cours</strong>
            <small>Texte ou PDF → résumé, points clés, glossaire. Gemini</small>
          </button>
          <button
            type="button"
            className="ai-action image"
            disabled={!canIllustrate || status?.illustration === false}
            onClick={onIllustrate}
          >
            <span className="ai-action-icon" aria-hidden="true">
              <span className="ti-image" />
            </span>
            <strong>Créer une illustration</strong>
            <small>Description → image pédagogique. Hugging Face</small>
          </button>
        </div>
        {blockedReason && (
          <p className="field-help">
            <span className="ti-lock" aria-hidden="true" /> {blockedReason}
          </p>
        )}
        <h3 className="ai-activity-title">Activité de cette fiche</h3>
        {jobs.length ? (
          <ul className="ai-jobs">
            {jobs.map((job) => (
              <JobItem
                key={job.id}
                job={job}
                canRate={canRate}
                onRated={onRated}
              />
            ))}
          </ul>
        ) : (
          <p className="field-help">
            Aucune génération pour l’instant. Les durées, la qualité mesurée et
            vos notes apparaîtront ici.
          </p>
        )}
      </div>
    </Modal>
  );
}
export function RunningBanner({ job }: { job: AIJob }) {
  const elapsed = useElapsed(job);
  const summary = job.kind === "SUMMARY";
  return (
    <div className="ai-running no-print" role="status" aria-live="polite">
      <span className="ai-running-orb" aria-hidden="true">
        <span className="ti-wand" />
      </span>
      <div>
        <strong>
          {summary
            ? "L’IA rédige le résumé de votre fiche…"
            : "L’IA dessine votre illustration…"}
        </strong>
        <span>
          {seconds(elapsed)} · Vous pouvez continuer à travailler, la fiche se
          mettra à jour automatiquement.
        </span>
      </div>
      <span className="ai-running-bar" aria-hidden="true" />
    </div>
  );
}
