import { useState } from "react";
import type { ReactNode } from "react";
import { Alert } from "../components/UI";
import {
  dayLabel,
  duration,
  groupByDay,
  percent,
  plural,
  timeRange,
} from "./format";
import {
  generators,
  planStatuses,
  priorities,
  taskSources,
  taskStatuses,
} from "./types";
import type {
  GoalMinutes,
  Plan,
  Priority,
  Progress,
  Task,
  TaskStatus,
} from "./types";

export function useAnnouncer() {
  const [message, setMessage] = useState({ text: "", id: 0 });
  return {
    message,
    announce: (text: string) =>
      setMessage((current) => ({ text, id: current.id + 1 })),
  };
}
export function LiveStatus({
  message,
}: {
  message: { text: string; id: number };
}) {
  return (
    <div
      className="planning-live"
      role="status"
      aria-live="polite"
      aria-atomic="true"
    >
      {message.text && (
        // A new node per message lets screen readers repeat an identical text.
        <p className="notice" key={message.id}>
          {message.text}
        </p>
      )}
    </div>
  );
}
export function LoadFailure({
  error,
  onRetry,
}: {
  error: unknown;
  onRetry: () => void;
}) {
  return (
    <section className="panel">
      <Alert error={error} />
      <button className="text-button" onClick={onRetry}>
        Réessayer le chargement
      </button>
    </section>
  );
}
export const statusAnnouncement = (task: Task) =>
  `Tâche « ${task.title} » : ${taskStatuses[task.status].toLowerCase()}.`;
export function PriorityBadge({
  priority,
  label,
}: {
  priority: Priority;
  label?: string;
}) {
  return (
    <span
      className={"status-badge planning-priority-" + priority.toLowerCase()}
    >
      {label || priorities[priority]}
    </span>
  );
}
export function PlanBadges({ plan }: { plan: Plan }) {
  return (
    <p className="planning-badges">
      <span
        className={"status-badge planning-plan-" + plan.status.toLowerCase()}
      >
        <span className="visually-hidden">Statut : </span>
        {plan.status_label || planStatuses[plan.status]}
      </span>
      <span className="status-badge">
        <span className="visually-hidden">Généré par : </span>
        {plan.generator_label || generators[plan.generator]}
      </span>
    </p>
  );
}
export function ProgressMetrics({
  progress,
  streak,
}: {
  progress: Progress;
  streak: number;
}) {
  return (
    <div className="metric-grid planning-metrics">
      <div className="metric-card">
        <span className="ti-stats-up" aria-hidden="true" />
        <div>
          <strong>{percent(progress.completion_rate)}</strong>
          <p>Taux de réalisation</p>
        </div>
      </div>
      <div className="metric-card">
        <span className="ti-timer" aria-hidden="true" />
        <div>
          <strong>
            <span className="planning-nowrap">
              {duration(progress.done_minutes)}
            </span>{" "}
            /{" "}
            <span className="planning-nowrap">
              {duration(progress.planned_minutes)}
            </span>
          </strong>
          <p>Temps réalisé / prévu</p>
        </div>
      </div>
      <div className="metric-card">
        <span className="ti-alarm-clock" aria-hidden="true" />
        <div>
          <strong>{progress.overdue}</strong>
          <p>{progress.overdue > 1 ? "Tâches en retard" : "Tâche en retard"}</p>
        </div>
      </div>
      <div className="metric-card">
        <span className="ti-bolt" aria-hidden="true" />
        <div>
          <strong>{plural(streak, "jour", "jours")}</strong>
          <p>Série de jours de révision</p>
        </div>
      </div>
    </div>
  );
}
export function GoalProgress({ goals }: { goals: GoalMinutes[] }) {
  return (
    <ul className="planning-goal-bars">
      {goals.map((goal) => {
        const done = duration(goal.done_minutes),
          planned = duration(goal.planned_minutes);
        return (
          <li key={goal.id}>
            <div>
              <strong>{goal.title}</strong>
              <span>
                {done} / {planned}
              </span>
            </div>
            <progress
              aria-label={`Avancement de « ${goal.title} » : ${done} réalisées sur ${planned} prévues`}
              value={Math.min(goal.done_minutes, goal.planned_minutes)}
              max={Math.max(goal.planned_minutes, 1)}
            />
          </li>
        );
      })}
    </ul>
  );
}
export function TaskStatusControls({
  task,
  saving = false,
  onChange,
}: {
  task: Task;
  saving?: boolean;
  onChange: (status: TaskStatus) => void;
}) {
  const when = timeRange(task.starts_at, task.ends_at);
  return (
    <div className="planning-status-controls">
      {(["DONE", "SKIPPED", "TODO"] as TaskStatus[]).map((status) => (
        <button
          key={status}
          type="button"
          aria-pressed={task.status === status}
          // Stays focusable while saving; a disabled button would drop focus.
          aria-disabled={saving || undefined}
          onClick={() => {
            if (!saving) onChange(status);
          }}
        >
          {taskStatuses[status]}
          <span className="visually-hidden">
            {" "}
            — {task.title}, {when}
          </span>
        </button>
      ))}
    </div>
  );
}
export function TaskItem({
  task,
  saving = false,
  children,
}: {
  task: Task;
  saving?: boolean;
  children?: ReactNode;
}) {
  return (
    <li
      className={"planning-task is-" + task.status.toLowerCase()}
      aria-busy={saving || undefined}
    >
      <p className="planning-task-time">
        {timeRange(task.starts_at, task.ends_at)}
        <small>{duration(task.minutes)}</small>
      </p>
      <div className="planning-task-body">
        <p className="planning-task-title">{task.title}</p>
        <p className="planning-task-meta">
          <span
            className={
              "status-badge planning-task-" + task.status.toLowerCase()
            }
          >
            {taskStatuses[task.status]}
          </span>
          {task.goal && <span>Objectif : {task.goal.title}</span>}
          {task.deadline && <span>Échéance : {task.deadline.title}</span>}
          <span>{taskSources[task.source]}</span>
        </p>
        {task.description && (
          <p className="planning-task-description">{task.description}</p>
        )}
        {saving && <p className="planning-task-saving">Enregistrement…</p>}
      </div>
      {children && <div className="planning-task-actions">{children}</div>}
    </li>
  );
}
export function TaskDays({
  tasks,
  render,
}: {
  tasks: Task[];
  render: (task: Task) => ReactNode;
}) {
  return (
    <div className="planning-days">
      {groupByDay(tasks).map(([day, items]) => (
        <div className="planning-day" key={day}>
          <h3>{dayLabel(day)}</h3>
          <ul className="planning-tasks">{items.map(render)}</ul>
        </div>
      ))}
    </div>
  );
}
