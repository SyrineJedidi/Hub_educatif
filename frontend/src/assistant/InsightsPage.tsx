import { useSearchParams } from "react-router-dom";
import { useResource } from "../hooks/useResource";
import { Alert, Empty, Field, Loading, Select } from "../components/UI";
import { insightsCsvUrl, insightsPath, settingsListPath } from "./api";
import { AssistantManagerNav, AssistantUnavailable } from "./AssistantRoutes";
import type { Insights, ManagedScope, MessageStatus } from "./types";
import { messageStatuses, sourceKinds, sourceTypes } from "./types";
import { count, day, duration, ratio, tunisDate } from "./format";
import { useAssistantContext } from "./useAssistantContext";
import "./assistant.css";
function CountTable({
  title,
  label,
  rows,
  empty,
}: {
  title: string;
  label: string;
  rows: { key: string; label: string; count: number }[];
  empty: string;
}) {
  return (
    <section className="panel">
      <h2>{title}</h2>
      {rows.length ? (
        <div
          className="table-scroll"
          role="region"
          aria-label={title}
          tabIndex={0}
        >
          <table className="assistant-table">
            <caption className="visually-hidden">{title}</caption>
            <thead>
              <tr>
                <th scope="col">{label}</th>
                <th scope="col">Nombre</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.key}>
                  <th scope="row" className="assistant-cell-text">
                    {row.label}
                  </th>
                  <td>{count(row.count)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <Empty>{empty}</Empty>
      )}
    </section>
  );
}
function Report({
  scope,
  from,
  to,
}: {
  scope: ManagedScope;
  from: string;
  to: string;
}) {
  const range = { from, to };
  const { data, error, loading, reload } = useResource<Insights>(
    insightsPath(scope.source_type, scope.scope_id, range),
  );
  if (loading && !data) return <Loading />;
  if (!data)
    return (
      <section className="panel">
        <Alert error={error} />
        <button className="text-button" onClick={reload}>
          Réessayer le chargement
        </button>
      </section>
    );
  const statuses = data.answers_by_status || {};
  const metrics: [string, string, string][] = [
    ["ti-comments", count(data.questions), "Questions posées"],
    ["ti-user", count(data.active_students), "Étudiants actifs"],
    ["ti-thumb-up", ratio(data.satisfaction), "Satisfaction (avis utiles)"],
    ["ti-na", ratio(data.out_of_scope_rate), "Questions hors cours"],
    ["ti-microphone", ratio(data.voice_share), "Questions dictées"],
    ["ti-timer", duration(data.latency_ms?.p50), "Temps de réponse médian"],
    ["ti-time", duration(data.latency_ms?.p95), "Temps de réponse (95 %)"],
    ["ti-flag", count(data.low_rated_answers), "Réponses mal notées"],
  ];
  return (
    <>
      <Alert error={error} />
      {loading && (
        <p className="field-help" role="status">
          Actualisation des chiffres…
        </p>
      )}
      <div className="metric-grid assistant-metrics">
        {metrics.map(([icon, value, label]) => (
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
        Les questions des étudiants sont anonymisées : aucun nom n’est affiché.
        Les essais des enseignants ne sont pas comptés. La satisfaction rapporte
        les avis « Utile » à l’ensemble des avis donnés
        {data.feedback
          ? " (" +
            data.feedback.up +
            " utiles, " +
            data.feedback.down +
            " à améliorer, dont " +
            data.feedback.shared +
            " partagés pour examen)"
          : ""}
        . Les jours sans question ne sont pas listés.
      </p>
      <div className="assistant-columns">
        <CountTable
          title="Réponses par statut"
          label="Statut"
          rows={(Object.keys(messageStatuses) as MessageStatus[]).map(
            (key) => ({
              key,
              label: messageStatuses[key],
              count: statuses[key] || 0,
            }),
          )}
          empty="Aucune réponse sur la période."
        />
        <CountTable
          title="Questions par jour"
          label="Jour"
          rows={(data.questions_per_day || [])
            .filter((row) => row.questions > 0)
            .map((row) => ({
              key: row.date,
              label: day(row.date),
              count: row.questions,
            }))}
          empty="Aucune question sur la période."
        />
      </div>
      <CountTable
        title="Sources les plus citées"
        label="Source"
        rows={(data.top_sources || []).map((row) => ({
          key: row.source_kind + row.source_id,
          label:
            row.title +
            " · " +
            (sourceKinds[row.source_kind] || row.source_kind),
          count: row.count,
        }))}
        empty="Aucune source citée sur la période."
      />
      <CountTable
        title="Questions restées sans réponse"
        label="Question (hors cours)"
        rows={(data.unanswered_questions || []).map((row, i) => ({
          key: i + row.question,
          label: row.question,
          count: row.count,
        }))}
        empty="Aucune question hors cours : le contenu couvre les questions posées."
      />
      <div className="assistant-empty-action">
        <a
          className="btn_one"
          href={insightsCsvUrl(scope.source_type, scope.scope_id, range)}
        >
          Exporter en CSV ↗
        </a>
      </div>
    </>
  );
}
export default function InsightsPage() {
  const { admin } = useAssistantContext();
  const [params, setParams] = useSearchParams();
  const scopes = useResource<{ results: ManagedScope[] }>(settingsListPath);
  const from = params.get("from") || tunisDate(-29),
    to = params.get("to") || tunisDate();
  if (!scopes.data && !scopes.loading)
    return (
      <AssistantUnavailable
        title="Suivi de l’assistant"
        error={scopes.error}
        onRetry={scopes.reload}
      />
    );
  const list = scopes.data?.results || [];
  const selected =
    list.find((s) => s.key === params.get("scope")) || list[0] || null;
  function update(key: string, value: string) {
    setParams(
      (current) => {
        const next = new URLSearchParams(current);
        if (value) next.set(key, value);
        else next.delete(key);
        return next;
      },
      { replace: true },
    );
  }
  const invalid = from > to;
  return (
    <div className="assistant-module">
      <div className="page-heading">
        <div>
          <p className="eyebrow">ASSISTANT PÉDAGOGIQUE</p>
          <h1>Suivi de l’assistant</h1>
          <p>
            Questions posées, qualité des réponses, notions que le contenu ne
            couvre pas encore : de quoi enrichir vos supports.
          </p>
        </div>
      </div>
      <AssistantManagerNav />
      {!scopes.data ? (
        <Loading />
      ) : !selected ? (
        <section className="panel">
          <Empty headingLevel={2} title="Aucun cours à suivre">
            {admin
              ? "Aucun groupe ni cours n’existe encore."
              : "Les groupes qui vous sont confiés et vos cours apparaîtront ici."}
          </Empty>
        </section>
      ) : (
        <>
          <section
            className="panel"
            aria-label="Choisir le cours et la période"
          >
            <div className="filters">
              <Select
                label="Cours"
                value={selected.key}
                onChange={(e) => update("scope", e.target.value)}
              >
                {list.map((s) => (
                  <option key={s.key} value={s.key}>
                    {s.title} · {sourceTypes[s.source_type]}
                  </option>
                ))}
              </Select>
              <Field
                label="Du"
                type="date"
                value={from}
                max={to}
                onChange={(e) => update("from", e.target.value)}
              />
              <Field
                label="Au"
                type="date"
                value={to}
                min={from}
                onChange={(e) => update("to", e.target.value)}
              />
            </div>
            <p className="field-help">
              Période de 180 jours au maximum ; par défaut, les 30 derniers
              jours.
            </p>
            {invalid && (
              <p className="notice notice-error" role="alert">
                La date de début doit précéder la date de fin.
              </p>
            )}
          </section>
          {!invalid && from && to && (
            <Report scope={selected} from={from} to={to} />
          )}
        </>
      )}
    </div>
  );
}
