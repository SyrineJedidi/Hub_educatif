import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { api, date, localDateTime } from "../api/client";
import { useResource } from "../hooks/useResource";
import {
  Alert,
  Empty,
  Field,
  Form,
  Loading,
  Modal,
  Select,
  Textarea,
} from "../components/UI";
import { usePlanningContext } from "./usePlanningContext";
import {
  LiveStatus,
  LoadFailure,
  PriorityBadge,
  useAnnouncer,
} from "./PlanningWidgets";
import { duration, plural, shortDate } from "./format";
import { deadlineKinds, goalStatuses, priorities } from "./types";
import type { Deadline, Goal, GroupReference, Reference } from "./types";
import {
  TITLE_MAX_LENGTH,
  changes,
  compact,
  integerOrText,
  isoOrEmpty,
  usePlanningForm,
  validateDeadline,
  validateGoal,
} from "./validation";
import "./planning.css";
type Dialog =
  | { kind: "goal"; goal?: Goal }
  | { kind: "delete-goal"; goal: Goal }
  | { kind: "deadline"; deadline?: Deadline }
  | { kind: "delete-deadline"; deadline: Deadline };
export default function ObjectivesPage() {
  const { apiBase, base } = usePlanningContext();
  const [status, setStatus] = useState(""),
    [past, setPast] = useState(false),
    [dialog, setDialog] = useState<Dialog | null>(null);
  const goals = useResource<{ results: Goal[] }>(apiBase + "goals/"),
    deadlines = useResource<{ results: Deadline[] }>(
      apiBase + "deadlines/" + (past ? "" : "?upcoming=true"),
    ),
    groups = useResource<{ results: GroupReference[] }>(apiBase + "groups/");
  const { message, announce } = useAnnouncer();
  const addGoal = useRef<HTMLButtonElement>(null),
    addDeadline = useRef<HTMLButtonElement>(null),
    focusAfterClose = useRef<HTMLElement | null>(null);
  useEffect(() => {
    // Runs after the dialog restored focus to a row that is about to disappear.
    if (!dialog && focusAfterClose.current) {
      focusAfterClose.current.focus();
      focusAfterClose.current = null;
    }
  }, [dialog]);
  const allGoals = goals.data?.results || [];
  const shownGoals = status
    ? allGoals.filter((goal) => goal.status === status)
    : allGoals;
  const shownDeadlines = [...(deadlines.data?.results || [])].sort(
    (a, b) => Date.parse(a.due_at) - Date.parse(b.due_at),
  );
  function saved(text: string, focus?: HTMLElement | null) {
    focusAfterClose.current = focus || null;
    setDialog(null);
    announce(text);
    goals.reload();
    deadlines.reload();
  }
  return (
    <div className="planning-module">
      <div className="page-heading">
        <div>
          <p className="eyebrow">PLANIFICATION ET COACHING</p>
          <h1>Objectifs et échéances</h1>
          <p>
            Fixez ce que vous voulez réussir et notez vos examens, quiz et
            devoirs : vos plannings s’appuient sur ces informations.
          </p>
        </div>
        <Link className="text-button" to={base}>
          Mon planning de révision ↗
        </Link>
      </div>
      <LiveStatus message={message} />
      <section className="panel" aria-labelledby="planning-goals-title">
        <div className="panel-heading">
          <h2 id="planning-goals-title">Mes objectifs</h2>
          <button
            ref={addGoal}
            className="btn_one"
            onClick={() => setDialog({ kind: "goal" })}
          >
            Ajouter un objectif +
          </button>
        </div>
        <div className="filters">
          <Select
            label="Statut des objectifs"
            value={status}
            onChange={(e) => setStatus(e.target.value)}
          >
            <option value="">Tous les objectifs</option>
            {Object.entries(goalStatuses).map(([key, label]) => (
              <option key={key} value={key}>
                {label}
              </option>
            ))}
          </Select>
        </div>
        {goals.loading && !goals.data ? (
          <Loading />
        ) : !goals.data ? (
          <LoadFailure error={goals.error} onRetry={goals.reload} />
        ) : (
          <>
            <Alert error={goals.error} />
            {shownGoals.length ? (
              <div
                className="table-scroll"
                role="region"
                aria-label="Tableau de mes objectifs"
                tabIndex={0}
              >
                <table className="planning-table">
                  <caption className="visually-hidden">
                    Mes objectifs de révision
                  </caption>
                  <thead>
                    <tr>
                      <th scope="col">Objectif</th>
                      <th scope="col">Groupe</th>
                      <th scope="col">Priorité</th>
                      <th scope="col">Statut</th>
                      <th scope="col">Réalisé / prévu</th>
                      <th scope="col">Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {shownGoals.map((goal) => (
                      <tr key={goal.id}>
                        <th scope="row">
                          {goal.title}
                          <small>
                            {goal.target_date &&
                              `Date cible : ${shortDate(goal.target_date)} · `}
                            {plural(
                              goal.estimated_hours,
                              "heure estimée",
                              "heures estimées",
                            )}
                          </small>
                        </th>
                        <td>
                          {goal.learning_group
                            ? goal.learning_group.name
                            : "Aucun groupe"}
                        </td>
                        <td>
                          <PriorityBadge
                            priority={goal.priority}
                            label={goal.priority_label}
                          />
                        </td>
                        <td>
                          <span
                            className={
                              "status-badge planning-goal-" +
                              goal.status.toLowerCase()
                            }
                          >
                            {goal.status_label || goalStatuses[goal.status]}
                          </span>
                        </td>
                        <td>
                          {duration(goal.done_minutes)} /{" "}
                          {duration(goal.planned_minutes)}
                        </td>
                        <td>
                          <div className="planning-row-actions">
                            <button
                              className="text-button"
                              onClick={() => setDialog({ kind: "goal", goal })}
                            >
                              Modifier
                              <span className="visually-hidden">
                                {" "}
                                l’objectif « {goal.title} »
                              </span>
                            </button>
                            <button
                              className="text-button"
                              onClick={() =>
                                setDialog({ kind: "delete-goal", goal })
                              }
                            >
                              Supprimer
                              <span className="visually-hidden">
                                {" "}
                                l’objectif « {goal.title} »
                              </span>
                            </button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <Empty
                title={
                  status ? "Aucun objectif pour ce statut" : "Aucun objectif"
                }
              >
                {status
                  ? "Choisissez un autre statut pour retrouver vos objectifs."
                  : "Ajoutez un premier objectif : une matière à consolider, un chapitre à maîtriser…"}
              </Empty>
            )}
          </>
        )}
      </section>
      <section className="panel" aria-labelledby="planning-deadlines-title">
        <div className="panel-heading">
          <h2 id="planning-deadlines-title">Mes échéances</h2>
          <button
            ref={addDeadline}
            className="btn_one"
            onClick={() => setDialog({ kind: "deadline" })}
          >
            Ajouter une échéance +
          </button>
        </div>
        <label className="planning-check">
          <input
            type="checkbox"
            checked={past}
            onChange={(e) => setPast(e.target.checked)}
          />
          Afficher aussi les échéances passées
        </label>
        {deadlines.loading && !deadlines.data ? (
          <Loading />
        ) : !deadlines.data ? (
          <LoadFailure error={deadlines.error} onRetry={deadlines.reload} />
        ) : (
          <>
            <Alert error={deadlines.error} />
            {shownDeadlines.length ? (
              <div
                className="table-scroll"
                role="region"
                aria-label="Tableau de mes échéances"
                tabIndex={0}
              >
                <table className="planning-table">
                  <caption className="visually-hidden">
                    Mes échéances : examens, quiz et devoirs
                  </caption>
                  <thead>
                    <tr>
                      <th scope="col">Échéance</th>
                      <th scope="col">Type</th>
                      <th scope="col">Date</th>
                      <th scope="col">Objectif</th>
                      <th scope="col">Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {shownDeadlines.map((deadline) => (
                      <tr key={deadline.id}>
                        <th scope="row">
                          {deadline.title}
                          {deadline.notes && (
                            <small className="planning-pre">
                              {deadline.notes}
                            </small>
                          )}
                        </th>
                        <td>
                          {deadline.kind_label || deadlineKinds[deadline.kind]}
                        </td>
                        <td>{date(deadline.due_at)}</td>
                        <td>
                          {deadline.goal
                            ? deadline.goal.title
                            : "Aucun objectif"}
                        </td>
                        <td>
                          <div className="planning-row-actions">
                            <button
                              className="text-button"
                              onClick={() =>
                                setDialog({ kind: "deadline", deadline })
                              }
                            >
                              Modifier
                              <span className="visually-hidden">
                                {" "}
                                l’échéance « {deadline.title} »
                              </span>
                            </button>
                            <button
                              className="text-button"
                              onClick={() =>
                                setDialog({ kind: "delete-deadline", deadline })
                              }
                            >
                              Supprimer
                              <span className="visually-hidden">
                                {" "}
                                l’échéance « {deadline.title} »
                              </span>
                            </button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <Empty title="Aucune échéance">
                {past
                  ? "Ajoutez vos examens, quiz et devoirs pour que vos plannings en tiennent compte."
                  : "Aucune échéance à venir. Ajoutez vos examens, quiz et devoirs pour que vos plannings en tiennent compte."}
              </Empty>
            )}
          </>
        )}
      </section>
      {dialog?.kind === "goal" && (
        <Modal
          title={dialog.goal ? "Modifier l’objectif" : "Ajouter un objectif"}
          onClose={() => setDialog(null)}
        >
          <Alert error={groups.error} />
          <GoalForm
            goal={dialog.goal}
            groups={groups.data?.results || []}
            onSaved={(title) =>
              saved(
                dialog.goal
                  ? `Objectif « ${title} » enregistré.`
                  : `Objectif « ${title} » ajouté.`,
              )
            }
          />
        </Modal>
      )}
      {dialog?.kind === "delete-goal" && (
        <Modal title="Supprimer cet objectif ?" onClose={() => setDialog(null)}>
          <p className="intro">
            L’objectif « {dialog.goal.title} » sera supprimé définitivement.
            S’il est déjà utilisé par des tâches de révision, la suppression
            sera refusée : marquez-le plutôt « Abandonné ».
          </p>
          <Form
            label="Confirmer la suppression"
            onSubmit={() =>
              api(apiBase + "goals/" + dialog.goal.id + "/", "DELETE")
            }
            onSuccess={() =>
              saved(
                `Objectif « ${dialog.goal.title} » supprimé.`,
                addGoal.current,
              )
            }
          />
        </Modal>
      )}
      {dialog?.kind === "deadline" && (
        <Modal
          title={
            dialog.deadline ? "Modifier l’échéance" : "Ajouter une échéance"
          }
          onClose={() => setDialog(null)}
        >
          <DeadlineForm
            deadline={dialog.deadline}
            goals={allGoals}
            onSaved={(title) =>
              saved(
                dialog.deadline
                  ? `Échéance « ${title} » enregistrée.`
                  : `Échéance « ${title} » ajoutée.`,
              )
            }
          />
        </Modal>
      )}
      {dialog?.kind === "delete-deadline" && (
        <Modal
          title="Supprimer cette échéance ?"
          onClose={() => setDialog(null)}
        >
          <p className="intro">
            L’échéance « {dialog.deadline.title} » sera supprimée
            définitivement. Les tâches de révision qui la préparent sont
            conservées.
          </p>
          <Form
            label="Confirmer la suppression"
            onSubmit={() =>
              api(apiBase + "deadlines/" + dialog.deadline.id + "/", "DELETE")
            }
            onSuccess={() =>
              saved(
                `Échéance « ${dialog.deadline.title} » supprimée.`,
                addDeadline.current,
              )
            }
          />
        </Modal>
      )}
    </div>
  );
}
function GoalForm({
  goal,
  groups,
  onSaved,
}: {
  goal?: Goal;
  groups: GroupReference[];
  onSaved: (title: string) => void;
}) {
  const { apiBase } = usePlanningContext();
  const form = usePlanningForm({
    title: goal?.title || "",
    description: goal?.description || "",
    learning_group_id: goal?.learning_group?.id || "",
    target_date: goal?.target_date || "",
    priority: goal?.priority || "MEDIUM",
    estimated_hours: String(goal?.estimated_hours ?? 5),
    status: goal?.status || "ACTIVE",
  });
  const { values, errors, change } = form;
  const current = goal?.learning_group;
  // Keep the saved group selectable even after the enrollment has ended.
  const options =
    current && !groups.some((group) => group.id === current.id)
      ? [...groups, current]
      : groups;
  const body = (v: typeof values) => ({
    title: v.title.trim(),
    description: v.description.trim(),
    learning_group_id: v.learning_group_id || null,
    target_date: v.target_date || null,
    priority: v.priority,
    estimated_hours: integerOrText(v.estimated_hours),
    ...(goal ? { status: v.status } : {}),
  });
  return (
    <Form
      formRef={form.formRef}
      noValidate
      clearErrorOnChange
      label={goal ? "Enregistrer l’objectif" : "Ajouter l’objectif"}
      onSubmit={() =>
        form.submit(validateGoal(values), async () => {
          if (!goal)
            return api(apiBase + "goals/", "POST", compact(body(values)));
          const changed = changes(body(values), body(form.initial));
          if (Object.keys(changed).length)
            return api(apiBase + "goals/" + goal.id + "/", "PATCH", changed);
        })
      }
      onSuccess={() => onSaved(values.title.trim())}
    >
      <p className="field-help">
        Seuls le titre et les heures estimées sont obligatoires.
      </p>
      <Field
        label="Titre"
        name="title"
        value={values.title}
        onChange={change("title")}
        maxLength={TITLE_MAX_LENGTH}
        required
        error={errors.title}
      />
      <Textarea
        label="Description"
        name="description"
        value={values.description}
        onChange={change("description")}
        maxLength={1000}
        rows={3}
        error={errors.description}
      />
      <Select
        label="Groupe"
        name="learning_group_id"
        value={values.learning_group_id}
        onChange={change("learning_group_id")}
        error={errors.learning_group_id}
      >
        <option value="">Aucun groupe</option>
        {options.map((group) => (
          <option key={group.id} value={group.id}>
            {group.name} · {group.code}
          </option>
        ))}
      </Select>
      <div className="form-grid">
        <Field
          label="Date cible"
          name="target_date"
          type="date"
          value={values.target_date}
          onChange={change("target_date")}
          error={errors.target_date}
        />
        <Select
          label="Priorité"
          name="priority"
          value={values.priority}
          onChange={change("priority")}
          error={errors.priority}
        >
          {Object.entries(priorities).map(([key, label]) => (
            <option key={key} value={key}>
              {label}
            </option>
          ))}
        </Select>
        <Field
          label="Heures estimées"
          name="estimated_hours"
          type="number"
          inputMode="numeric"
          min={1}
          max={200}
          step={1}
          value={values.estimated_hours}
          onChange={change("estimated_hours")}
          required
          error={errors.estimated_hours}
        />
        {goal && (
          <Select
            label="Statut"
            name="status"
            value={values.status}
            onChange={change("status")}
            error={errors.status}
          >
            {Object.entries(goalStatuses).map(([key, label]) => (
              <option key={key} value={key}>
                {label}
              </option>
            ))}
          </Select>
        )}
      </div>
    </Form>
  );
}
function DeadlineForm({
  deadline,
  goals,
  onSaved,
}: {
  deadline?: Deadline;
  goals: Goal[];
  onSaved: (title: string) => void;
}) {
  const { apiBase } = usePlanningContext();
  const form = usePlanningForm({
    title: deadline?.title || "",
    kind: deadline?.kind || "EXAM",
    due_at: deadline ? localDateTime(deadline.due_at) : "",
    goal_id: deadline?.goal?.id || "",
    notes: deadline?.notes || "",
  });
  const { values, errors, change } = form;
  const current = deadline?.goal;
  const options: (Reference & { suffix?: string })[] = goals.map((goal) => ({
    id: goal.id,
    title: goal.title,
    suffix: goal.status === "ACTIVE" ? "" : goalStatuses[goal.status],
  }));
  if (current && !options.some((goal) => goal.id === current.id))
    options.push(current);
  const body = (v: typeof values) => ({
    title: v.title.trim(),
    kind: v.kind,
    due_at: isoOrEmpty(v.due_at),
    goal_id: v.goal_id || null,
    notes: v.notes.trim(),
  });
  return (
    <Form
      formRef={form.formRef}
      noValidate
      clearErrorOnChange
      label={deadline ? "Enregistrer l’échéance" : "Ajouter l’échéance"}
      onSubmit={() =>
        form.submit(
          validateDeadline(
            values,
            !deadline || values.due_at !== form.initial.due_at,
          ),
          async () => {
            if (!deadline)
              return api(apiBase + "deadlines/", "POST", compact(body(values)));
            const changed = changes(body(values), body(form.initial));
            if (Object.keys(changed).length)
              return api(
                apiBase + "deadlines/" + deadline.id + "/",
                "PATCH",
                changed,
              );
          },
        )
      }
      onSuccess={() => onSaved(values.title.trim())}
    >
      <Field
        label="Titre"
        name="title"
        value={values.title}
        onChange={change("title")}
        maxLength={TITLE_MAX_LENGTH}
        required
        error={errors.title}
      />
      <div className="form-grid">
        <Select
          label="Type"
          name="kind"
          value={values.kind}
          onChange={change("kind")}
          required
          error={errors.kind}
        >
          {Object.entries(deadlineKinds).map(([key, label]) => (
            <option key={key} value={key}>
              {label}
            </option>
          ))}
        </Select>
        <Field
          label="Date et heure"
          name="due_at"
          type="datetime-local"
          value={values.due_at}
          min={localDateTime(new Date().toISOString())}
          onChange={change("due_at")}
          required
          error={errors.due_at}
        />
      </div>
      <Select
        label="Objectif"
        name="goal_id"
        value={values.goal_id}
        onChange={change("goal_id")}
        error={errors.goal_id}
      >
        <option value="">Aucun objectif</option>
        {options.map((goal) => (
          <option key={goal.id} value={goal.id}>
            {goal.title}
            {goal.suffix ? ` (${goal.suffix})` : ""}
          </option>
        ))}
      </Select>
      <Textarea
        label="Notes"
        name="notes"
        value={values.notes}
        onChange={change("notes")}
        maxLength={500}
        rows={3}
        error={errors.notes}
      />
      <p className="field-help">
        Heure de Tunis. Une échéance créée ou déplacée doit être à venir.
      </p>
    </Form>
  );
}
