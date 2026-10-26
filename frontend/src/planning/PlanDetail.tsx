import { useEffect, useRef, useState } from "react";
import { Link, useLocation, useNavigate, useParams } from "react-router-dom";
import { api, ApiError, date } from "../api/client";
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
import { useTaskStatus } from "./useTaskStatus";
import {
  LiveStatus,
  PlanBadges,
  TaskDays,
  TaskItem,
  TaskStatusControls,
  statusAnnouncement,
  useAnnouncer,
} from "./PlanningWidgets";
import {
  count,
  dayKey,
  dayLabel,
  duration,
  paragraphs,
  period,
  plural,
  seconds,
  time,
  timeRange,
  today,
} from "./format";
import { goalStatuses } from "./types";
import type {
  Deadline,
  Goal,
  Plan,
  PlanDetail as PlanData,
  Reference,
  Task,
} from "./types";
import {
  TITLE_MAX_LENGTH,
  changes,
  compact,
  isoOrEmpty,
  usePlanningForm,
  validateTask,
  validateTitle,
} from "./validation";
import "./planning.css";
type Dialog =
  | { kind: "activate" | "archive" | "delete" | "rename" }
  | { kind: "task"; task?: Task }
  | { kind: "delete-task"; task: Task };
function generationLine(plan: Plan) {
  if (plan.generator !== "AI")
    return "Calculé par règles à partir de vos priorités, de vos échéances et de vos disponibilités.";
  const tokens = [
    plan.prompt_tokens !== null &&
      `${count(plan.prompt_tokens)} jetons envoyés`,
    plan.output_tokens !== null &&
      `${count(plan.output_tokens)} jetons générés`,
  ].filter(Boolean);
  return (
    `Généré par ${plan.model_name || "Gemini"}` +
    (plan.latency_ms !== null ? ` en ${seconds(plan.latency_ms)}` : "") +
    (tokens.length ? ` · ${tokens.join(" · ")}` : "")
  );
}
const taskLabel = (task: Task) =>
  `la tâche « ${task.title} » du ${dayLabel(dayKey(task.starts_at)).toLowerCase()}, ${timeRange(task.starts_at, task.ends_at)}`;
export default function PlanDetail() {
  const { id } = useParams();
  const { apiBase, base } = usePlanningContext(),
    navigate = useNavigate(),
    location = useLocation();
  const generated = !!(location.state as { generated?: boolean } | null)
    ?.generated;
  const {
    data: plan,
    error,
    loading,
    reload,
  } = useResource<PlanData>(apiBase + "plans/" + id + "/");
  const { message, announce } = useAnnouncer();
  const status = useTaskStatus(plan, (task) => {
    announce(statusAnnouncement(task));
    reload();
  });
  const [dialog, setDialog] = useState<Dialog | null>(null);
  const addTask = useRef<HTMLButtonElement>(null),
    tasksTitle = useRef<HTMLHeadingElement>(null),
    focusAfterClose = useRef<HTMLElement | null>(null);
  useEffect(() => {
    if (!dialog && focusAfterClose.current) {
      focusAfterClose.current.focus();
      focusAfterClose.current = null;
    }
  }, [dialog]);
  if (loading && !plan) return <Loading />;
  if (!plan)
    return (
      <div className="planning-module">
        <div className="page-heading">
          <div>
            <p className="eyebrow">PLANNING DE RÉVISION</p>
            <h1>
              {error instanceof ApiError && error.status === 404
                ? "Planning introuvable"
                : "Planning indisponible"}
            </h1>
          </div>
          <Link className="text-button" to={base + "/plannings"}>
            Mes plannings ↗
          </Link>
        </div>
        <Alert error={error} />
        <button className="text-button" onClick={reload}>
          Réessayer le chargement
        </button>
      </div>
    );
  const editable = plan.status !== "ARCHIVED",
    active = plan.status === "ACTIVE";
  function saved(text: string, focus?: HTMLElement | null) {
    focusAfterClose.current = focus || null;
    setDialog(null);
    announce(text);
    reload();
  }
  const action = (path: string, text: string) => (
    <Form
      label={text}
      onSubmit={() =>
        api(apiBase + "plans/" + plan.id + "/" + path, "POST", {})
      }
      onSuccess={() =>
        saved(
          path === "activate/"
            ? "Planning activé : suivez vos tâches depuis votre tableau de bord."
            : "Planning archivé : il reste consultable en lecture seule.",
        )
      }
    />
  );
  return (
    <div className="planning-module">
      <div className="page-heading">
        <div>
          <p className="eyebrow">PLANNING DE RÉVISION</p>
          <h1>{plan.title}</h1>
          <p>{period(plan.start_date, plan.end_date)}</p>
        </div>
        <Link className="text-button" to={base + "/plannings"}>
          Mes plannings ↗
        </Link>
      </div>
      <LiveStatus message={message} />
      <Alert error={error} />
      <Alert error={status.error} />
      {generated && plan.status === "DRAFT" && (
        <p className="notice">
          Planning généré en brouillon : vérifiez les tâches, ajustez-les si
          besoin, puis activez-le pour suivre votre avancement.
        </p>
      )}
      <section className="panel" aria-labelledby="planning-summary-title">
        <h2 id="planning-summary-title">Résumé</h2>
        <PlanBadges plan={plan} />
        {plan.fallback_reason && (
          <p className="notice planning-fallback">{plan.fallback_reason}</p>
        )}
        <p className="planning-generation">{generationLine(plan)}</p>
        <p className="planning-muted">
          {plan.done_count} /{" "}
          {plural(plan.tasks_count, "tâche terminée", "tâches terminées")} ·{" "}
          {duration(plan.planned_minutes)} prévues
          {plan.activated_at && ` · activé le ${date(plan.activated_at)}`}
        </p>
        <div className="actions planning-plan-actions">
          {plan.status === "DRAFT" && (
            <button
              className="btn_one"
              onClick={() => setDialog({ kind: "activate" })}
            >
              Activer
            </button>
          )}
          {editable && (
            <button
              className="text-button"
              onClick={() => setDialog({ kind: "rename" })}
            >
              Renommer
            </button>
          )}
          {editable && (
            <button
              className="text-button"
              onClick={() => setDialog({ kind: "archive" })}
            >
              Archiver
            </button>
          )}
          {!active && (
            <button
              className="text-button"
              onClick={() => setDialog({ kind: "delete" })}
            >
              Supprimer
            </button>
          )}
          <a
            className="text-button"
            href={"/api/" + apiBase + "plans/" + plan.id + "/ics/"}
          >
            Exporter vers mon agenda (.ics) ↗
          </a>
        </div>
        {!editable && (
          <p className="notice">
            Ce planning est archivé : il reste consultable en lecture seule.
          </p>
        )}
      </section>
      {plan.advice && (
        <section
          className="panel planning-advice"
          aria-labelledby="planning-advice-title"
        >
          <h2 id="planning-advice-title">Conseils pour ce planning</h2>
          {paragraphs(plan.advice).map((text, index) => (
            <p key={index}>{text}</p>
          ))}
        </section>
      )}
      <section className="panel" aria-labelledby="planning-tasks-title">
        <div className="panel-heading">
          <h2 id="planning-tasks-title" ref={tasksTitle} tabIndex={-1}>
            Tâches du planning
          </h2>
          {editable && (
            <button
              ref={addTask}
              className="btn_one"
              onClick={() => setDialog({ kind: "task" })}
            >
              Ajouter une tâche +
            </button>
          )}
        </div>
        {plan.status === "DRAFT" && (
          <p className="field-help">
            Brouillon : ajoutez, modifiez ou supprimez librement les tâches.
            Activez le planning pour suivre vos tâches au quotidien.
          </p>
        )}
        {plan.tasks.length ? (
          <TaskDays
            tasks={plan.tasks}
            render={(task) => {
              const current = status.view(task),
                saving = !!status.saving[task.id];
              return (
                <TaskItem key={task.id} task={current} saving={saving}>
                  {editable && (
                    <>
                      {active && (
                        <TaskStatusControls
                          task={current}
                          saving={saving}
                          onChange={(value) => void status.change(task, value)}
                        />
                      )}
                      <div className="planning-row-actions">
                        <button
                          className="text-button"
                          onClick={() =>
                            setDialog({ kind: "task", task: current })
                          }
                        >
                          Modifier
                          <span className="visually-hidden">
                            {" "}
                            {taskLabel(current)}
                          </span>
                        </button>
                        <button
                          className="text-button"
                          onClick={() =>
                            setDialog({ kind: "delete-task", task: current })
                          }
                        >
                          Supprimer
                          <span className="visually-hidden">
                            {" "}
                            {taskLabel(current)}
                          </span>
                        </button>
                      </div>
                    </>
                  )}
                </TaskItem>
              );
            }}
          />
        ) : (
          <Empty title="Aucune tâche">
            {editable
              ? "Ajoutez une tâche pour réserver un moment de révision dans ce planning."
              : "Ce planning ne contient aucune tâche."}
          </Empty>
        )}
      </section>
      {dialog?.kind === "activate" && (
        <Modal title="Activer ce planning ?" onClose={() => setDialog(null)}>
          <p className="intro">
            Ses tâches apparaîtront dans votre tableau de bord et vous pourrez
            les marquer terminées ou ignorées. Si un autre planning est actif,
            il sera archivé.
          </p>
          {action("activate/", "Confirmer l’activation")}
        </Modal>
      )}
      {dialog?.kind === "archive" && (
        <Modal title="Archiver ce planning ?" onClose={() => setDialog(null)}>
          <p className="intro">
            Le planning et ses tâches seront conservés en lecture seule.
            {active &&
              " Vous n’aurez plus de planning actif tant que vous n’en activerez pas un autre."}
          </p>
          {action("archive/", "Confirmer l’archivage")}
        </Modal>
      )}
      {dialog?.kind === "delete" && (
        <Modal title="Supprimer ce planning ?" onClose={() => setDialog(null)}>
          <p className="intro">
            Le planning « {plan.title} » et ses{" "}
            {plural(plan.tasks_count, "tâche", "tâches")} seront supprimés
            définitivement.
          </p>
          <Form
            label="Confirmer la suppression"
            onSubmit={() => api(apiBase + "plans/" + plan.id + "/", "DELETE")}
            onSuccess={() => navigate(base + "/plannings", { replace: true })}
          />
        </Modal>
      )}
      {dialog?.kind === "rename" && (
        <Modal title="Renommer le planning" onClose={() => setDialog(null)}>
          <RenameForm
            plan={plan}
            onSaved={(title) => saved(`Planning renommé « ${title} ».`)}
          />
        </Modal>
      )}
      {dialog?.kind === "task" && (
        <Modal
          title={dialog.task ? "Modifier la tâche" : "Ajouter une tâche"}
          onClose={() => setDialog(null)}
        >
          <TaskForm
            plan={plan}
            task={dialog.task}
            onSaved={(title) =>
              saved(
                dialog.task
                  ? `Tâche « ${title} » enregistrée.`
                  : `Tâche « ${title} » ajoutée.`,
              )
            }
          />
        </Modal>
      )}
      {dialog?.kind === "delete-task" && (
        <Modal title="Supprimer cette tâche ?" onClose={() => setDialog(null)}>
          <p className="intro">
            {taskLabel(dialog.task).charAt(0).toUpperCase() +
              taskLabel(dialog.task).slice(1)}{" "}
            sera supprimée définitivement.
          </p>
          <Form
            label="Confirmer la suppression"
            onSubmit={() =>
              api(apiBase + "tasks/" + dialog.task.id + "/", "DELETE")
            }
            onSuccess={() =>
              saved(
                `Tâche « ${dialog.task.title} » supprimée.`,
                addTask.current || tasksTitle.current,
              )
            }
          />
        </Modal>
      )}
    </div>
  );
}
function RenameForm({
  plan,
  onSaved,
}: {
  plan: PlanData;
  onSaved: (title: string) => void;
}) {
  const { apiBase } = usePlanningContext();
  const form = usePlanningForm({ title: plan.title });
  const { values, errors, change } = form;
  return (
    <Form
      formRef={form.formRef}
      noValidate
      clearErrorOnChange
      label="Enregistrer le titre"
      onSubmit={() =>
        form.submit(validateTitle(values.title), () =>
          api(apiBase + "plans/" + plan.id + "/", "PATCH", {
            title: values.title.trim(),
          }),
        )
      }
      onSuccess={() => onSaved(values.title.trim())}
    >
      <Field
        label="Titre du planning"
        name="title"
        value={values.title}
        onChange={change("title")}
        maxLength={TITLE_MAX_LENGTH}
        required
        error={errors.title}
      />
    </Form>
  );
}
// Keeps a link the user did not touch selectable even if its target left the list.
function withCurrent(options: Reference[], current?: Reference | null) {
  return current && !options.some((option) => option.id === current.id)
    ? [...options, current]
    : options;
}
function TaskForm({
  plan,
  task,
  onSaved,
}: {
  plan: PlanData;
  task?: Task;
  onSaved: (title: string) => void;
}) {
  const { apiBase } = usePlanningContext();
  const goals = useResource<{ results: Goal[] }>(apiBase + "goals/"),
    deadlines = useResource<{ results: Deadline[] }>(apiBase + "deadlines/");
  const day = today();
  const form = usePlanningForm({
    title: task?.title || "",
    description: task?.description || "",
    goal_id: task?.goal?.id || "",
    deadline_id: task?.deadline?.id || "",
    day: task
      ? dayKey(task.starts_at)
      : day >= plan.start_date && day <= plan.end_date
        ? day
        : plan.start_date,
    starts_at: task ? time(task.starts_at) : "18:00",
    ends_at: task ? time(task.ends_at) : "19:00",
  });
  const { values, errors, change } = form;
  if ((goals.loading && !goals.data) || (deadlines.loading && !deadlines.data))
    return <Loading />;
  const goalOptions = withCurrent(
    (goals.data?.results || []).map((goal) => ({
      id: goal.id,
      title:
        goal.status === "ACTIVE"
          ? goal.title
          : `${goal.title} (${goalStatuses[goal.status]})`,
    })),
    task?.goal,
  );
  const deadlineOptions = withCurrent(
    (deadlines.data?.results || []).map((deadline) => ({
      id: deadline.id,
      title: `${deadline.title} · ${date(deadline.due_at)}`,
    })),
    task?.deadline,
  );
  const body = (v: typeof values) => ({
    title: v.title.trim(),
    description: v.description.trim(),
    goal_id: v.goal_id || null,
    deadline_id: v.deadline_id || null,
    starts_at: isoOrEmpty(v.day + "T" + v.starts_at.slice(0, 5)),
    ends_at: isoOrEmpty(v.day + "T" + v.ends_at.slice(0, 5)),
  });
  return (
    <>
      <Alert error={goals.error || deadlines.error} />
      <Form
        formRef={form.formRef}
        noValidate
        clearErrorOnChange
        label={task ? "Enregistrer la tâche" : "Ajouter la tâche"}
        onSubmit={() =>
          form.submit(validateTask(values, plan), async () => {
            if (!task)
              return api(
                apiBase + "plans/" + plan.id + "/tasks/",
                "POST",
                compact(body(values)),
              );
            const changed = changes(body(values), body(form.initial));
            if (Object.keys(changed).length)
              return api(apiBase + "tasks/" + task.id + "/", "PATCH", changed);
          })
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
        <Textarea
          label="Description"
          name="description"
          value={values.description}
          onChange={change("description")}
          maxLength={1000}
          rows={3}
          error={errors.description}
        />
        <div className="form-grid">
          <Select
            label="Objectif"
            name="goal_id"
            value={values.goal_id}
            onChange={change("goal_id")}
            error={errors.goal_id}
          >
            <option value="">Aucun objectif</option>
            {goalOptions.map((goal) => (
              <option key={goal.id} value={goal.id}>
                {goal.title}
              </option>
            ))}
          </Select>
          <Select
            label="Échéance liée"
            name="deadline_id"
            value={values.deadline_id}
            onChange={change("deadline_id")}
            error={errors.deadline_id}
          >
            <option value="">Aucune échéance</option>
            {deadlineOptions.map((deadline) => (
              <option key={deadline.id} value={deadline.id}>
                {deadline.title}
              </option>
            ))}
          </Select>
        </div>
        <Field
          label="Jour"
          name="day"
          type="date"
          min={plan.start_date}
          max={plan.end_date}
          value={values.day}
          onChange={change("day")}
          required
          error={errors.day}
        />
        <div className="form-grid">
          <Field
            label="Début"
            name="starts_at"
            type="time"
            value={values.starts_at}
            onChange={change("starts_at")}
            required
            error={errors.starts_at}
          />
          <Field
            label="Fin"
            name="ends_at"
            type="time"
            value={values.ends_at}
            onChange={change("ends_at")}
            required
            error={errors.ends_at}
          />
        </div>
        <p className="field-help">
          De 15 min à 4 h, le même jour, dans la période du planning et sans
          chevaucher une autre tâche (heure de Tunis).
        </p>
      </Form>
    </>
  );
}
