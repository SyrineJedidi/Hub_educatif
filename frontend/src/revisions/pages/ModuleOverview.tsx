import { useState } from "react";
import { Link } from "react-router-dom";
import { api, date } from "../../api/client";
import { useResource } from "../../hooks/useResource";
import { Alert, Loading } from "../../components/UI";
import type { AIJob, Facets, SheetSummary } from "../types";
import { seconds } from "../types";
import { AiPill, StatusPill } from "./SheetTable";
import { JobStatusPill, jobLabel } from "./JobJournal";
import { useSheetContext } from "../hooks/useSheetContext";
import "../styles/backoffice.css";
interface Overview {
  stats: Facets["stats"];
  illustrations: { total: number; ai: number };
  to_review_count: number;
  to_review: SheetSummary[];
  ready_to_publish: SheetSummary[];
  recent: SheetSummary[];
  running: AIJob[];
  recent_jobs: AIJob[];
}
/** Home of the module back-office: figures, to-do lists and every feature one click away. */
export default function ModuleOverview() {
  const { admin, base, paths, user } = useSheetContext();
  const { data, error, loading, reload } = useResource<Overview>("revisions/overview/");
  const [busy, setBusy] = useState(""),
    [actionError, setActionError] = useState<unknown>(),
    [message, setMessage] = useState("");
  async function publish(sheet: SheetSummary) {
    setBusy(sheet.id);
    setActionError(undefined);
    try {
      await api("sheets/" + sheet.id + "/publish/", "POST", {});
      setMessage("« " + sheet.title + " » est publiée : les étudiants du groupe la voient.");
      reload();
    } catch (err) {
      setActionError(err);
    } finally {
      setBusy("");
    }
  }
  if (loading && !data) return <Loading />;
  const stats = data?.stats;
  const kpis: [string, string, number | undefined, string][] = [
    ["ti-files", "Fiches", stats?.total, ""],
    ["ti-share", "Publiées", stats?.published, "good"],
    ["ti-pencil-alt", "Brouillons", stats?.draft, ""],
    ["ti-alert", "IA à relire", data?.to_review_count, data?.to_review_count ? "warn" : ""],
    ["ti-gallery", "Illustrations", data?.illustrations.total, ""],
    ["ti-wand", "Générations en cours", data?.running.length, data?.running.length ? "ai" : ""],
  ];
  const features = [
    [paths.sheets, "ti-files", "Gestion des fiches", "Tableau complet : créer, consulter, modifier, dupliquer, publier, archiver, supprimer — une par une ou en groupe."],
    [paths.workshop, "ti-wand", "Atelier IA", "Un cours (texte ou PDF) devient une fiche : résumé Gemini, points clés, glossaire et illustration Hugging Face."],
    [paths.library, "ti-gallery", "Médiathèque", "Toutes les illustrations, importées ou générées, avec leur description accessible."],
    [paths.followUp, "ti-stats-up", "Suivi des étudiants", "Qui a lu chaque fiche publiée, qui l’a révisée avec les cartes mémoire et son niveau de maîtrise."],
    [paths.journal, "ti-list", "Journal des générations", "Chaque appel IA tracé : moteur, temps d’attente, durée, qualité mesurée, note."],
    [paths.stats, "ti-pulse", admin ? "Pilotage de l’IA" : "Statistiques IA", "Taux de réussite, latence p50/p95, couverture des mots-clés, compression, notes."],
    [paths.reading, "ti-book", "Bibliothèque de lecture", "La vue des fiches telle que la consultent les étudiants, avec le mode révision par cartes."],
    [admin ? "/administration/roles" : "/gestion/droits", "ti-key", admin ? "Rôles et permissions" : "Mes droits", "Ce que chaque rôle peut faire, vérifié par le serveur à chaque requête."],
  ];
  return (
    <div className="bo-page">
      <header className="bo-page-head">
        <div>
          <p className="bo-eyebrow">Module · Résumés et illustrations</p>
          <h1>Vue d’ensemble</h1>
          <p>
            Bonjour {user?.first_name}. Voici l’état de {admin ? "toutes les fiches de la plateforme" : "vos fiches de révision"} et
            ce qui demande votre attention.
          </p>
        </div>
        <div className="bo-head-actions">
          <Link className="bo-btn bo-btn-primary" to={base + "/nouvelle"}>
            <span className="ti-plus" aria-hidden="true" /> Nouvelle fiche
          </Link>
          <Link className="bo-btn bo-btn-ai" to={paths.workshop}>
            <span className="ti-wand" aria-hidden="true" /> Créer avec l’IA
          </Link>
        </div>
      </header>
      <Alert error={error || actionError} success={message} />
      <dl className="bo-kpis">
        {kpis.map(([icon, label, value, tone]) => (
          <div key={label} className={"bo-kpi " + tone}>
            <span className={icon} aria-hidden="true" />
            <dt>{label}</dt>
            <dd>{value ?? "—"}</dd>
          </div>
        ))}
      </dl>
      <section className="bo-card" aria-labelledby="lifecycle-title">
        <h2 id="lifecycle-title" className="bo-card-title">Cycle de vie d’une fiche</h2>
        <ol className="bo-lifecycle">
          <li>
            <span className="ti-pencil-alt" aria-hidden="true" />
            <strong>Brouillon</strong>
            <small>Rédigée à la main ou par l’IA. Visible par vous seul.</small>
          </li>
          <li>
            <span className="ti-check-box" aria-hidden="true" />
            <strong>Relecture</strong>
            <small>Un contenu IA doit être relu : le serveur bloque sinon la publication.</small>
          </li>
          <li>
            <span className="ti-share" aria-hidden="true" />
            <strong>Publiée</strong>
            <small>Lisible par les étudiants inscrits au groupe, en lecture seule.</small>
          </li>
          <li>
            <span className="ti-archive" aria-hidden="true" />
            <strong>Archivée</strong>
            <small>Conservée en lecture seule ; restaurable en brouillon.</small>
          </li>
        </ol>
      </section>
      <div className="bo-columns">
        <section className="bo-card" aria-labelledby="review-title">
          <h2 id="review-title" className="bo-card-title">
            <span className="ti-alert" aria-hidden="true" /> À relire avant publication
          </h2>
          {data?.to_review.length ? (
            <ul className="bo-list">
              {data.to_review.map((s) => (
                <li key={s.id}>
                  <div>
                    <Link to={base + "/" + s.id}>{s.title}</Link>
                    <small>{s.learning_group_name || "Personnelle"} · {date(s.updated_at)}</small>
                  </div>
                  <Link className="bo-btn bo-btn-small" to={base + "/" + s.id}>
                    Relire
                  </Link>
                </li>
              ))}
            </ul>
          ) : (
            <p className="bo-muted bo-pad">Aucun contenu IA en attente de relecture.</p>
          )}
        </section>
        <section className="bo-card" aria-labelledby="ready-title">
          <h2 id="ready-title" className="bo-card-title">
            <span className="ti-share" aria-hidden="true" /> Prêtes à publier
          </h2>
          {data?.ready_to_publish.length ? (
            <ul className="bo-list">
              {data.ready_to_publish.map((s) => (
                <li key={s.id}>
                  <div>
                    <Link to={base + "/" + s.id}>{s.title}</Link>
                    <small>{s.learning_group_name} · {s.key_point_count} points clés · {s.illustration_count} image(s)</small>
                  </div>
                  <button type="button" className="bo-btn bo-btn-small bo-btn-primary" onClick={() => void publish(s)} disabled={busy === s.id}>
                    {busy === s.id ? "Publication…" : "Publier"}
                  </button>
                </li>
              ))}
            </ul>
          ) : (
            <p className="bo-muted bo-pad">Aucun brouillon complet en attente.</p>
          )}
        </section>
      </div>
      <section aria-labelledby="features-title">
        <h2 id="features-title" className="bo-section-heading">Fonctionnalités du module</h2>
        <ul className="bo-features">
          {features.map(([to, icon, title, text]) => (
            <li key={title}>
              <Link to={to}>
                <span className={"bo-feature-icon " + icon} aria-hidden="true" />
                <strong>{title}</strong>
                <small>{text}</small>
                <span className="bo-feature-go" aria-hidden="true">Ouvrir <span className="ti-arrow-right" /></span>
              </Link>
            </li>
          ))}
        </ul>
      </section>
      <div className="bo-columns">
        <section className="bo-card" aria-labelledby="recent-title">
          <h2 id="recent-title" className="bo-card-title">Dernières fiches modifiées</h2>
          <ul className="bo-list">
            {data?.recent.map((s) => (
              <li key={s.id}>
                <div>
                  <Link to={base + "/" + s.id}>{s.title}</Link>
                  <small>{s.course_label} · {date(s.updated_at)}</small>
                </div>
                <span className="bo-list-pills">
                  <StatusPill status={s.status} />
                  <AiPill sheet={s} />
                </span>
              </li>
            ))}
          </ul>
          <Link className="bo-card-link" to={paths.sheets}>
            Toutes les fiches <span className="ti-arrow-right" aria-hidden="true" />
          </Link>
        </section>
        <section className="bo-card" aria-labelledby="jobs-title">
          <h2 id="jobs-title" className="bo-card-title">Activité IA récente</h2>
          {data?.recent_jobs.length ? (
            <ul className="bo-list">
              {data.recent_jobs.map((j) => (
                <li key={j.id}>
                  <div>
                    <strong className="bo-row-strong">{jobLabel(j)}</strong>
                    <small>{j.sheet_title} · {seconds(j.duration_ms)}</small>
                  </div>
                  <JobStatusPill job={j} />
                </li>
              ))}
            </ul>
          ) : (
            <p className="bo-muted bo-pad">Aucune génération pour l’instant.</p>
          )}
          <Link className="bo-card-link" to={paths.journal}>
            Journal complet <span className="ti-arrow-right" aria-hidden="true" />
          </Link>
        </section>
      </div>
    </div>
  );
}
