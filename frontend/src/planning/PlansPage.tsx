import { useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api, date, query } from "../api/client";
import type { Page } from "../api/types";
import { useResource } from "../hooks/useResource";
import {
  Alert,
  Empty,
  Field,
  Form,
  Loading,
  Pagination,
  Select,
} from "../components/UI";
import { usePlanningContext } from "./usePlanningContext";
import { LoadFailure, PlanBadges } from "./PlanningWidgets";
import { addDays, duration, percent, period, plural, today } from "./format";
import { planStatuses } from "./types";
import type { GenerationMode, Plan, PlanDetail, PlannerContext } from "./types";
import {
  TITLE_MAX_LENGTH,
  compact,
  usePlanningForm,
  validateGeneration,
} from "./validation";
import "./planning.css";
export default function PlansPage() {
  const { apiBase, base } = usePlanningContext();
  const context = useResource<PlannerContext>(apiBase + "context/");
  const [status, setStatus] = useState(""),
    [page, setPage] = useState(1);
  const plans = useResource<Page<Plan>>(
    apiBase + "plans/?" + query({ status, page }),
  );
  return (
    <div className="planning-module">
      <div className="page-heading">
        <div>
          <p className="eyebrow">PLANIFICATION ET COACHING</p>
          <h1>Mes plannings</h1>
          <p>
            Générez un programme de révision personnalisé, vérifiez-le, puis
            activez-le pour suivre vos tâches au quotidien.
          </p>
        </div>
        <Link className="text-button" to={base}>
          Mon planning de révision ↗
        </Link>
      </div>
      <div className="planning-columns">
        <GenerationPanel context={context.data} />
        <ContextPreview
          context={context.data}
          error={context.error}
          loading={context.loading}
          onRetry={context.reload}
        />
      </div>
      <section className="panel" aria-labelledby="planning-history-title">
        <div className="panel-heading">
          <h2 id="planning-history-title">Historique de mes plannings</h2>
        </div>
        <div className="filters">
          <Select
            label="Statut des plannings"
            value={status}
            onChange={(e) => {
              setStatus(e.target.value);
              setPage(1);
            }}
          >
            <option value="">Tous les plannings</option>
            {Object.entries(planStatuses).map(([key, label]) => (
              <option key={key} value={key}>
                {label}
              </option>
            ))}
          </Select>
        </div>
        {plans.loading && !plans.data ? (
          <Loading />
        ) : !plans.data ? (
          <LoadFailure error={plans.error} onRetry={plans.reload} />
        ) : (
          <>
            <Alert error={plans.error} />
            {plans.data.results.length ? (
              <>
                <p className="field-help">
                  {plural(plans.data.count, "planning", "plannings")}
                  {status ? " pour ce statut." : " au total."}
                </p>
                <ul className="planning-plans">
                  {plans.data.results.map((plan) => (
                    <PlanCard plan={plan} key={plan.id} />
                  ))}
                </ul>
                <Pagination
                  page={page}
                  count={plans.data.count}
                  onChange={setPage}
                />
              </>
            ) : (
              <Empty
                title={
                  status ? "Aucun planning pour ce statut" : "Aucun planning"
                }
              >
                {status
                  ? "Choisissez un autre statut pour retrouver vos plannings."
                  : "Votre premier planning sera généré à partir de vos objectifs, de vos échéances et de vos disponibilités."}
              </Empty>
            )}
          </>
        )}
      </section>
    </div>
  );
}
function PlanCard({ plan }: { plan: Plan }) {
  const { base } = usePlanningContext();
  return (
    <li className="planning-plan">
      <h3>
        <Link to={base + "/plannings/" + plan.id}>{plan.title}</Link>
      </h3>
      <PlanBadges plan={plan} />
      <p className="planning-muted">{period(plan.start_date, plan.end_date)}</p>
      <p className="planning-muted">
        {plan.done_count} /{" "}
        {plural(plan.tasks_count, "tâche terminée", "tâches terminées")} ·{" "}
        {duration(plan.planned_minutes)} prévues
      </p>
      <progress
        aria-label={`Tâches terminées du planning « ${plan.title} »`}
        value={plan.done_count}
        max={Math.max(plan.tasks_count, 1)}
      />
      <p className="planning-muted">Créé le {date(plan.created_at)}</p>
    </li>
  );
}
function GenerationPanel({ context }: { context: PlannerContext | null }) {
  const { apiBase, base } = usePlanningContext(),
    navigate = useNavigate();
  const start = today();
  const form = usePlanningForm({
    title: "",
    start_date: start,
    end_date: addDays(start, 6),
  });
  const { values, errors, change } = form;
  const [chosen, setChosen] = useState<GenerationMode | "">(""),
    [generating, setGenerating] = useState(false);
  const created = useRef("");
  const aiReady =
    !context || (context.ai.configured && context.ai.remaining_today > 0);
  // Without a usable AI the rules are the honest default; an explicit choice always wins.
  const mode: GenerationMode = chosen || (aiReady ? "ai" : "rules");
  async function generate() {
    const plan = await form.submit(validateGeneration(values), async () => {
      setGenerating(true);
      try {
        return await api<PlanDetail>(
          apiBase + "plans/generate/",
          "POST",
          compact({
            title: values.title.trim(),
            start_date: values.start_date,
            end_date: values.end_date,
            mode,
          }),
        );
      } finally {
        setGenerating(false);
      }
    });
    created.current = plan.id;
  }
  return (
    <section className="panel" aria-labelledby="planning-generate-title">
      <h2 id="planning-generate-title">Générer un nouveau planning</h2>
      <Form
        formRef={form.formRef}
        noValidate
        clearErrorOnChange
        label="Générer le planning"
        onSubmit={generate}
        onSuccess={() =>
          navigate(base + "/plannings/" + created.current, {
            state: { generated: true },
          })
        }
      >
        <Field
          label="Titre (facultatif)"
          name="title"
          value={values.title}
          onChange={change("title")}
          maxLength={TITLE_MAX_LENGTH}
          placeholder="Par exemple : Révisions de la semaine"
          error={errors.title}
        />
        <div className="form-grid">
          <Field
            label="Début"
            name="start_date"
            type="date"
            min={start}
            value={values.start_date}
            onChange={change("start_date")}
            required
            error={errors.start_date}
          />
          <Field
            label="Fin"
            name="end_date"
            type="date"
            min={values.start_date || start}
            value={values.end_date}
            onChange={change("end_date")}
            required
            error={errors.end_date}
          />
        </div>
        <p className="field-help">De 1 à 28 jours, à partir d’aujourd’hui.</p>
        <fieldset className="planning-modes">
          <legend>Mode de génération</legend>
          {(
            [
              [
                "ai",
                "Avec l’IA (Gemini)",
                "Un programme personnalisé selon vos cours, vos résultats aux quiz et votre temps disponible. En cas d’indisponibilité, le calcul par règles prend le relais.",
              ],
              [
                "rules",
                "Par règles",
                "Un calcul immédiat qui répartit vos objectifs selon leur priorité et leurs échéances.",
              ],
            ] as [GenerationMode, string, string][]
          ).map(([value, label, help]) => (
            <label
              key={value}
              className={
                "planning-mode" + (mode === value ? " is-selected" : "")
              }
            >
              <input
                type="radio"
                name="mode"
                value={value}
                checked={mode === value}
                onChange={() => setChosen(value)}
                aria-labelledby={"planning-mode-" + value}
                aria-describedby={"planning-mode-" + value + "-help"}
              />
              <span>
                <strong id={"planning-mode-" + value}>{label}</strong>
                <small id={"planning-mode-" + value + "-help"}>{help}</small>
              </span>
            </label>
          ))}
        </fieldset>
        <p className="planning-generating" role="status" aria-live="polite">
          {generating
            ? mode === "ai"
              ? "Gemini prépare votre programme…"
              : "Calcul du planning…"
            : ""}
        </p>
      </Form>
    </section>
  );
}
function ContextPreview({
  context,
  error,
  loading,
  onRetry,
}: {
  context: PlannerContext | null;
  error: unknown;
  loading: boolean;
  onRetry: () => void;
}) {
  const { base } = usePlanningContext();
  return (
    <section
      className="panel planning-context"
      aria-labelledby="planning-context-title"
    >
      <h2 id="planning-context-title">Ce que le planning prendra en compte</h2>
      {loading && !context ? (
        <Loading />
      ) : !context ? (
        <>
          <Alert error={error} />
          <button className="text-button" onClick={onRetry}>
            Réessayer le chargement
          </button>
        </>
      ) : (
        <>
          <dl className="planning-facts">
            <div>
              <dt>Objectifs en cours</dt>
              <dd>{context.goals}</dd>
            </div>
            <div>
              <dt>Échéances à venir</dt>
              <dd>{context.deadlines}</dd>
            </div>
            <div>
              <dt>Disponibilités</dt>
              <dd>{duration(context.weekly_minutes)} / semaine</dd>
            </div>
            <div>
              <dt>Résultats de quiz</dt>
              <dd>{context.quiz_results.length}</dd>
            </div>
          </dl>
          {!context.goals && !context.deadlines && (
            <p className="notice">
              Ajoutez au moins un objectif en cours ou une échéance avant de
              générer un planning.{" "}
              <Link to={base + "/objectifs"}>Objectifs et échéances ↗</Link>
            </p>
          )}
          {!context.weekly_minutes && (
            <p className="notice">
              Aucune disponibilité : ajoutez des créneaux pour que le planning
              puisse placer vos tâches.{" "}
              <Link to={base + "/disponibilites"}>Mes disponibilités ↗</Link>
            </p>
          )}
          <h3>Résultats récents</h3>
          {context.quiz_results.length ? (
            <ul className="planning-context-list">
              {context.quiz_results.slice(0, 5).map((result) => (
                <li key={result.quiz_title + result.submitted_at}>
                  {result.quiz_title} ({result.group_name}) :{" "}
                  <strong>{percent(result.percent)}</strong>
                </li>
              ))}
            </ul>
          ) : (
            <p className="planning-muted">Aucun quiz terminé pour le moment.</p>
          )}
          <p>
            {context.weak_groups.length
              ? `À renforcer en priorité : ${context.weak_groups.join(", ")}.`
              : "Aucun groupe ne présente de résultat faible."}
          </p>
          <h3>Cours</h3>
          {!context.courses_available ? (
            <p className="planning-muted">
              Le module de cours n’est pas encore disponible : le programme
              s’appuie sur vos objectifs, vos échéances et vos résultats.
            </p>
          ) : context.courses.length ? (
            <ul className="planning-context-list">
              {context.courses.map((course) => (
                <li key={course.title}>
                  {course.title} ·{" "}
                  {plural(course.chapters, "chapitre", "chapitres")}
                </li>
              ))}
            </ul>
          ) : (
            <p className="planning-muted">
              Aucun cours visible pour le moment.
            </p>
          )}
          <h3>Intelligence artificielle</h3>
          <p>
            {!context.ai.configured
              ? "L’IA n’est pas configurée sur ce serveur : le planning sera calculé par règles."
              : context.ai.remaining_today > 0
                ? `${context.ai.model || "Gemini"} · ${plural(context.ai.remaining_today, "génération restante", "générations restantes")} aujourd’hui.`
                : "Quota IA du jour atteint : le planning sera calculé par règles."}
          </p>
        </>
      )}
    </section>
  );
}
