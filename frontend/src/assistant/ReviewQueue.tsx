import { Link, useSearchParams } from "react-router-dom";
import { date } from "../api/client";
import type { Page } from "../api/types";
import { useResource } from "../hooks/useResource";
import { Alert, Empty, Loading, Pagination, Select } from "../components/UI";
import { reviewsPath, settingsListPath } from "./api";
import { AssistantManagerNav } from "./AssistantRoutes";
import type { FeedbackStatus, ManagedScope, Reason, Review } from "./types";
import { feedbackStatuses, ratings, reasons } from "./types";
import { excerpt, plural, reasonLabels } from "./format";
import { useAssistantContext } from "./useAssistantContext";
import "./assistant.css";
export default function ReviewQueue() {
  const { base } = useAssistantContext();
  const [params, setParams] = useSearchParams();
  // NEW by default: the queue is what still waits for a decision.
  const status = params.get("status") ?? "NEW",
    scope = params.get("scope") || "",
    reason = params.get("reason") || "",
    page = Math.max(1, Number(params.get("page")) || 1);
  const scopes = useResource<{ results: ManagedScope[] }>(settingsListPath);
  const { data, error, loading, reload } = useResource<Page<Review>>(
    reviewsPath({ status, scope, reason, page }),
  );
  function update(next: Record<string, string>) {
    setParams(
      (current) => {
        const result = new URLSearchParams(current);
        for (const [key, value] of Object.entries(next)) result.set(key, value);
        if (!result.get("page") || result.get("page") === "1")
          result.delete("page");
        for (const key of ["scope", "reason"])
          if (!result.get(key)) result.delete(key);
        return result;
      },
      { replace: true },
    );
  }
  const filtered = status !== "NEW" || !!scope || !!reason;
  return (
    <div className="assistant-module">
      <div className="page-heading">
        <div>
          <p className="eyebrow">RETOURS SUR LES RÉPONSES</p>
          <h1>Signalements</h1>
          <p>
            Les retours que les étudiants ont choisi de partager, sans leur
            identité. Confirmez la réponse, publiez une correction que
            l’assistant citera en priorité, ou classez sans suite.
          </p>
        </div>
      </div>
      <AssistantManagerNav />
      <section className="panel" aria-label="Filtrer les signalements">
        <div className="filters">
          <Select
            label="Statut"
            value={status}
            onChange={(e) => update({ status: e.target.value, page: "" })}
          >
            <option value="">Tous les statuts</option>
            {(Object.keys(feedbackStatuses) as FeedbackStatus[]).map((key) => (
              <option key={key} value={key}>
                {feedbackStatuses[key]}
              </option>
            ))}
          </Select>
          <Select
            label="Cours"
            value={scope}
            onChange={(e) => update({ scope: e.target.value, page: "" })}
          >
            <option value="">Tous les cours</option>
            {(scopes.data?.results || []).map((s) => (
              <option key={s.key} value={s.key}>
                {s.title}
              </option>
            ))}
          </Select>
          <Select
            label="Motif"
            value={reason}
            onChange={(e) => update({ reason: e.target.value, page: "" })}
          >
            <option value="">Tous les motifs</option>
            {(Object.keys(reasons) as Reason[]).map((key) => (
              <option key={key} value={key}>
                {reasons[key]}
              </option>
            ))}
          </Select>
        </div>
        {filtered && (
          <button
            className="text-button"
            onClick={() =>
              update({ status: "NEW", scope: "", reason: "", page: "" })
            }
          >
            Revenir aux signalements à traiter
          </button>
        )}
        <Alert error={scopes.error} />
      </section>
      {loading && !data ? (
        <Loading />
      ) : !data ? (
        <section className="panel">
          <Alert error={error} />
          <button className="text-button" onClick={reload}>
            Réessayer le chargement
          </button>
        </section>
      ) : data.results.length ? (
        <section className="panel">
          <div className="panel-heading">
            <h2>{plural(data.count, "signalement", "signalements")}</h2>
            <button className="text-button" onClick={reload}>
              Actualiser la liste
            </button>
          </div>
          <Alert error={error} />
          <ul className="assistant-reviews">
            {data.results.map((review) => (
              <li key={review.id}>
                <article className="assistant-review-card">
                  <h3>
                    <Link to={base + "/signalements/" + review.id}>
                      {excerpt(review.question, 140)}
                    </Link>
                  </h3>
                  <p className="assistant-badges">
                    <span className="status-badge">
                      {review.status_label || feedbackStatuses[review.status]}
                    </span>
                    <span className="status-badge assistant-badge-warning">
                      {ratings[review.rating]}
                    </span>
                    {reasonLabels(review).map((label) => (
                      <span key={label} className="status-badge">
                        {label}
                      </span>
                    ))}
                  </p>
                  <p className="assistant-meta">
                    {review.scope_title} · signalé le {date(review.created_at)}
                  </p>
                  {review.comment && (
                    <p className="assistant-review-comment">
                      « {excerpt(review.comment, 200)} »
                    </p>
                  )}
                  <Link
                    className="text-button"
                    to={base + "/signalements/" + review.id}
                  >
                    {review.status === "NEW" ? "Examiner" : "Consulter"}
                    <span className="visually-hidden">
                      {" "}
                      le signalement du {date(review.created_at)} :{" "}
                      {excerpt(review.question, 80)}
                    </span>{" "}
                    ↗
                  </Link>
                </article>
              </li>
            ))}
          </ul>
          <Pagination
            page={page}
            count={data.count}
            onChange={(p) => update({ page: String(p) })}
          />
        </section>
      ) : (
        <section className="panel">
          <Empty
            headingLevel={2}
            title={filtered ? "Aucun résultat" : "Aucun signalement à traiter"}
          >
            {filtered
              ? "Aucun signalement ne correspond à ces critères."
              : "Les retours partagés par vos étudiants apparaîtront ici."}
          </Empty>
        </section>
      )}
    </div>
  );
}
