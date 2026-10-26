import { useId, useState } from "react";
import { date } from "../api/client";
import { useResource } from "../hooks/useResource";
import {
  Empty,
  Field,
  Form,
  Loading,
  Select,
  Textarea,
  val,
} from "../components/UI";
import { saveSettings, settingsListPath } from "./api";
import { AssistantManagerNav, AssistantUnavailable } from "./AssistantRoutes";
import type { ManagedScope, Mode } from "./types";
import { modeHelp, modes, sourceTypes } from "./types";
import { personName } from "./format";
import { useAssistantContext } from "./useAssistantContext";
import "./assistant.css";
const SUGGESTIONS = 5;
function Check({
  name,
  label,
  help,
  defaultChecked,
}: {
  name: string;
  label: string;
  help: string;
  defaultChecked: boolean;
}) {
  const id = useId();
  return (
    <div className="field">
      <label className="assistant-check">
        <input
          type="checkbox"
          name={name}
          defaultChecked={defaultChecked}
          aria-describedby={id}
        />
        {label}
      </label>
      <p id={id} className="field-help assistant-check-help">
        {help}
      </p>
    </div>
  );
}
function ScopeSettings({
  scope,
  admin,
  onSaved,
}: {
  scope: ManagedScope;
  admin: boolean;
  onSaved: (scope: ManagedScope) => void;
}) {
  const heading = useId(),
    limitHelp = useId();
  return (
    <section className="panel assistant-settings" aria-labelledby={heading}>
      <div className="panel-heading">
        <div>
          <p className="eyebrow">{sourceTypes[scope.source_type]}</p>
          <h2 id={heading}>{scope.title}</h2>
          {admin && scope.teacher && (
            <p className="field-help">
              Enseignant : {personName(scope.teacher)}
            </p>
          )}
        </div>
        <span
          className={
            "status-badge " +
            (scope.enabled ? "assistant-badge-info" : "assistant-badge-error")
          }
        >
          {scope.enabled ? "Assistant activé" : "Assistant désactivé"}
        </span>
      </div>
      <Form
        label="Enregistrer les paramètres"
        onSubmit={async (form) => {
          const saved = await saveSettings(scope.source_type, scope.scope_id, {
            enabled: form.get("enabled") === "on",
            default_mode: val(form, "default_mode") as Mode,
            allow_mode_choice: form.get("allow_mode_choice") === "on",
            daily_question_limit: Number(val(form, "daily_question_limit")),
            block_during_quiz: form.get("block_during_quiz") === "on",
            suggested_questions: form
              .getAll("suggested_questions")
              .map((value) => String(value).trim())
              .filter(Boolean),
            welcome_message: val(form, "welcome_message").trim(),
          });
          if (saved) onSaved(saved);
        }}
      >
        <div className="assistant-settings-grid">
          <div>
            <Check
              name="enabled"
              label="Activer l’assistant pour ce cours"
              help="Désactivé, l’assistant refuse les nouvelles questions ; l’historique reste consultable."
              defaultChecked={scope.enabled}
            />
            <Check
              name="allow_mode_choice"
              label="Laisser les étudiants choisir le mode de réponse"
              help="Sinon, toutes les conversations utilisent le mode par défaut."
              defaultChecked={scope.allow_mode_choice}
            />
            <Check
              name="block_during_quiz"
              label="Suspendre l’assistant pendant un quiz en cours"
              help="Un étudiant qui a une tentative de quiz ouverte dans ce groupe ne peut plus poser de question jusqu’à la fin de sa tentative."
              defaultChecked={scope.block_during_quiz}
            />
          </div>
          <div>
            <Select
              label="Mode par défaut"
              name="default_mode"
              defaultValue={scope.default_mode}
            >
              {(Object.keys(modes) as Mode[]).map((value) => (
                <option key={value} value={value}>
                  {modes[value]} — {modeHelp[value]}
                </option>
              ))}
            </Select>
            <Field
              label="Questions par étudiant et par jour"
              name="daily_question_limit"
              type="number"
              min={1}
              max={200}
              required
              defaultValue={scope.daily_question_limit}
              aria-describedby={limitHelp}
            />
            <p id={limitHelp} className="field-help">
              Entre 1 et 200.
              {scope.max_daily_question_limit
                ? " Plafond fixé par l’établissement : " +
                  scope.max_daily_question_limit +
                  " questions par jour."
                : ""}
              {scope.effective_daily_limit != null
                ? " Limite appliquée aujourd’hui : " +
                  scope.effective_daily_limit +
                  "."
                : ""}
            </p>
          </div>
        </div>
        <fieldset className="assistant-suggestions">
          <legend>Questions suggérées (5 au maximum)</legend>
          <p className="field-help">
            Proposées aux étudiants au début d’une conversation. Laissez vide
            pour ne rien proposer.
          </p>
          <div className="assistant-suggestion-grid">
            {Array.from({ length: SUGGESTIONS }, (_, i) => (
              <Field
                key={i}
                label={"Question suggérée " + (i + 1)}
                name="suggested_questions"
                maxLength={200}
                defaultValue={scope.suggested_questions[i] || ""}
              />
            ))}
          </div>
        </fieldset>
        <Textarea
          label="Message d’accueil"
          name="welcome_message"
          rows={3}
          maxLength={500}
          defaultValue={scope.welcome_message}
          placeholder="Par exemple : posez vos questions sur le chapitre en cours, je réponds à partir des notes de votre enseignant."
        />
        {scope.updated_at && (
          <p className="field-help">
            Dernière modification le {date(scope.updated_at)}.
          </p>
        )}
      </Form>
    </section>
  );
}
export default function SettingsPage() {
  const { admin } = useAssistantContext();
  const { data, error, loading, reload } = useResource<{
    results: ManagedScope[];
  }>(settingsListPath);
  const [search, setSearch] = useState(""),
    [saved, setSaved] = useState<Record<string, ManagedScope>>({});
  if (!data && !loading)
    return (
      <AssistantUnavailable
        title="Paramètres de l’assistant"
        error={error}
        onRetry={reload}
      />
    );
  const scopes = (data?.results || []).map((s) => saved[s.key] || s);
  const term = search.trim().toLocaleLowerCase("fr");
  const shown = term
    ? scopes.filter((s) => s.title.toLocaleLowerCase("fr").includes(term))
    : scopes;
  return (
    <div className="assistant-module">
      <div className="page-heading">
        <div>
          <p className="eyebrow">ASSISTANT PÉDAGOGIQUE</p>
          <h1>Paramètres de l’assistant</h1>
          <p>
            Pour chaque cours et chaque groupe : activation, mode de réponse,
            limite quotidienne, suspension pendant les quiz et questions
            suggérées.
          </p>
        </div>
      </div>
      <AssistantManagerNav />
      {!data ? (
        <Loading />
      ) : !scopes.length ? (
        <section className="panel">
          <Empty headingLevel={2} title="Aucun cours à paramétrer">
            {admin
              ? "Aucun groupe ni cours n’existe encore."
              : "Les groupes qui vous sont confiés et vos cours apparaîtront ici."}
          </Empty>
        </section>
      ) : (
        <>
          {scopes.length > 3 && (
            <section className="panel" aria-label="Filtrer les cours">
              <Field
                label="Rechercher un cours ou un groupe"
                type="search"
                value={search}
                maxLength={100}
                onChange={(e) => setSearch(e.target.value)}
              />
              <p className="field-help" role="status">
                {shown.length} sur {scopes.length} affichés.
              </p>
            </section>
          )}
          {shown.map((scope) => (
            <ScopeSettings
              key={scope.key}
              scope={scope}
              admin={admin}
              onSaved={(next) =>
                setSaved((current) => ({ ...current, [scope.key]: next }))
              }
            />
          ))}
        </>
      )}
    </div>
  );
}
