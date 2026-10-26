import { useResource } from "../hooks/useResource";
import { Alert, Empty, Loading } from "../components/UI";
import { usagePath } from "./api";
import { AssistantManagerNav } from "./AssistantRoutes";
import type { ProviderStatus, Usage } from "./types";
import { errorCodes, llmProviders } from "./types";
import { count, day } from "./format";
import "./assistant.css";
const whisperProviders: Record<string, string> = {
  disabled: "Désactivée",
  fake: "Simulée (tests)",
  local: "Whisper local",
  groq: "Whisper via Groq",
};
function ProviderFacts({
  title,
  status,
  names,
}: {
  title: string;
  status?: ProviderStatus;
  names: Record<string, string>;
}) {
  return (
    <div className="assistant-provider">
      <h3>{title}</h3>
      {status ? (
        <dl className="assistant-facts">
          <div>
            <dt>Fournisseur</dt>
            <dd>{names[status.provider] || status.provider}</dd>
          </div>
          <div>
            <dt>Modèle</dt>
            <dd>
              {status.model || "—"}
              {status.fallback_model && (
                <small>Repli : {status.fallback_model}</small>
              )}
            </dd>
          </div>
          <div>
            <dt>Prêt à l’emploi</dt>
            <dd>{status.configured ? "Oui" : "Non"}</dd>
          </div>
        </dl>
      ) : (
        <p>État indisponible.</p>
      )}
    </div>
  );
}
export default function AdminUsage() {
  const { data, error, loading, reload } = useResource<Usage>(usagePath);
  const days = (data?.days || []).filter(
    (row) => row.questions || row.gemini_calls || row.failures,
  );
  const totals = data?.totals;
  const llm = data?.providers?.llm,
    budget = data?.limits?.global_daily_budget;
  const failures = Object.entries(data?.failures_by_code || {});
  return (
    <div className="assistant-module">
      <div className="page-heading">
        <div>
          <p className="eyebrow">ADMINISTRATION</p>
          <h1>Assistant pédagogique</h1>
          <p>
            Utilisation sur les 30 derniers jours, appels au modèle de langage
            et état des fournisseurs. Les conversations des étudiants ne sont
            jamais affichées.
          </p>
        </div>
      </div>
      <AssistantManagerNav />
      {loading && !data ? (
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
          <Alert error={error} />
          <section className="panel" aria-labelledby="usage-provider">
            <div className="panel-heading">
              <h2 id="usage-provider">Fournisseurs</h2>
              <button className="text-button" onClick={reload}>
                Actualiser
              </button>
            </div>
            <div className="assistant-columns">
              <ProviderFacts
                title="Réponses (Gemini)"
                status={llm}
                names={llmProviders}
              />
              <ProviderFacts
                title="Questions vocales (Whisper)"
                status={data.providers?.transcription}
                names={whisperProviders}
              />
            </div>
            {llm && !llm.configured && (
              <p className="notice">
                Aucun modèle de langage n’est prêt : les questions couvertes par
                le cours reçoivent une réponse « Échec ». Les questions hors
                cours sont toujours détectées sans appel au modèle.
              </p>
            )}
            {data.limits && (
              <dl className="assistant-facts assistant-limits">
                {budget && (
                  <div>
                    <dt>Budget global du jour</dt>
                    <dd>
                      {count(budget.used)} / {count(budget.limit)} appels
                    </dd>
                  </div>
                )}
                {data.limits.daily_questions_per_user != null && (
                  <div>
                    <dt>Plafond par étudiant et par cours</dt>
                    <dd>
                      {count(data.limits.daily_questions_per_user)} questions
                      par jour
                    </dd>
                  </div>
                )}
                {data.limits.voice_per_hour != null && (
                  <div>
                    <dt>Questions vocales</dt>
                    <dd>
                      {count(data.limits.voice_per_hour)} par heure,{" "}
                      {count(data.limits.max_audio_seconds)} s au plus
                    </dd>
                  </div>
                )}
              </dl>
            )}
          </section>
          {totals && (
            <div className="metric-grid">
              {(
                [
                  ["ti-comments", totals.questions, "Questions"],
                  ["ti-bolt", totals.gemini_calls, "Appels au modèle"],
                  ["ti-alert", totals.failures, "Échecs"],
                  [
                    "ti-stats-up",
                    totals.prompt_tokens + totals.output_tokens,
                    "Jetons consommés",
                  ],
                ] as const
              ).map(([icon, value, label]) => (
                <div className="metric-card" key={label}>
                  <span className={icon} aria-hidden="true" />
                  <div>
                    <strong>{count(value)}</strong>
                    <p>{label}</p>
                  </div>
                </div>
              ))}
            </div>
          )}
          <section className="panel" aria-labelledby="usage-days">
            <h2 id="usage-days">Utilisation par jour</h2>
            {days.length ? (
              <div
                className="table-scroll"
                role="region"
                aria-label="Tableau de l’utilisation par jour"
                tabIndex={0}
              >
                <table className="assistant-table">
                  <caption className="visually-hidden">
                    Questions, appels, échecs et jetons des jours d’activité
                  </caption>
                  <thead>
                    <tr>
                      <th scope="col">Jour</th>
                      <th scope="col">Questions</th>
                      <th scope="col">Appels au modèle</th>
                      <th scope="col">Échecs</th>
                      <th scope="col">Jetons (entrée / sortie)</th>
                    </tr>
                  </thead>
                  <tbody>
                    {days.map((row) => (
                      <tr key={row.date}>
                        <th scope="row">{day(row.date)}</th>
                        <td>{count(row.questions)}</td>
                        <td>{count(row.gemini_calls)}</td>
                        <td>{count(row.failures)}</td>
                        <td>
                          {count(row.prompt_tokens)} /{" "}
                          {count(row.output_tokens)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <Empty>Aucune question sur les 30 derniers jours.</Empty>
            )}
          </section>
          <div className="assistant-columns">
            <section className="panel" aria-labelledby="usage-failures">
              <h2 id="usage-failures">Échecs par cause</h2>
              {failures.length ? (
                <ul className="assistant-count-list">
                  {failures.map(([code, total]) => (
                    <li key={code}>
                      <span>{errorCodes[code] || code}</span>
                      <strong>{count(total)}</strong>
                    </li>
                  ))}
                </ul>
              ) : (
                <Empty title="Aucun échec">
                  Tous les appels au modèle ont abouti.
                </Empty>
              )}
            </section>
            <section className="panel" aria-labelledby="usage-scopes">
              <h2 id="usage-scopes">Cours les plus sollicités</h2>
              {data.top_scopes?.length ? (
                <ul className="assistant-count-list">
                  {data.top_scopes.map((row) => (
                    <li key={row.scope_key}>
                      <span>{row.title || "Cours sans titre"}</span>
                      <strong>
                        {count(row.questions)}
                        <span className="visually-hidden"> questions</span>
                      </strong>
                    </li>
                  ))}
                </ul>
              ) : (
                <Empty>Aucune question sur la période.</Empty>
              )}
            </section>
          </div>
        </>
      )}
    </div>
  );
}
