import { Link } from "react-router-dom";
import { date } from "../api/client";
import { useResource } from "../hooks/useResource";
import { Alert, Empty, Loading } from "../components/UI";
import { usePlanningContext } from "./usePlanningContext";
import { useTaskStatus } from "./useTaskStatus";
import {
  GoalProgress,
  LiveStatus,
  LoadFailure,
  PlanBadges,
  ProgressMetrics,
  TaskDays,
  TaskItem,
  TaskStatusControls,
  statusAnnouncement,
  useAnnouncer,
} from "./PlanningWidgets";
import { dayLabel, duration, period, plural, today } from "./format";
import type { Dashboard } from "./types";
import "./planning.css";
export default function PlanningDashboard() {
  const { base, apiBase } = usePlanningContext();
  const { data, error, loading, reload } = useResource<Dashboard>(
    apiBase + "dashboard/",
  );
  const { message, announce } = useAnnouncer();
  const status = useTaskStatus(data, (task) => {
    announce(statusAnnouncement(task));
    reload();
  });
  const todayIds = new Set(data?.today.map((task) => task.id));
  const upcoming = (data?.upcoming || []).filter(
    (task) => !todayIds.has(task.id),
  );
  return (
    <div className="planning-module">
      <div className="page-heading">
        <div>
          <p className="eyebrow">PLANIFICATION ET COACHING</p>
          <h1>Mon planning de révision</h1>
          <p>
            Vos objectifs, vos créneaux et vos tâches du jour, réunis au même
            endroit pour réviser à votre rythme.
          </p>
        </div>
      </div>
      <nav
        className="planning-quick-links"
        aria-label="Organiser mes révisions"
      >
        {[
          [
            "ti-target",
            "Objectifs et échéances",
            "Ce que vous voulez réussir, et pour quand.",
            base + "/objectifs",
          ],
          [
            "ti-time",
            "Disponibilités",
            "Vos créneaux de révision de la semaine.",
            base + "/disponibilites",
          ],
          [
            "ti-agenda",
            "Mes plannings",
            "Générer, activer et exporter vos programmes.",
            base + "/plannings",
          ],
        ].map(([icon, title, text, path]) => (
          <Link key={path} to={path}>
            <span className={icon} aria-hidden="true" />
            <span>
              <strong>{title}</strong>
              <small>{text}</small>
            </span>
            <span aria-hidden="true">↗</span>
          </Link>
        ))}
      </nav>
      <LiveStatus message={message} />
      <Alert error={status.error} />
      {loading && !data ? (
        <Loading />
      ) : !data ? (
        <LoadFailure error={error} onRetry={reload} />
      ) : (
        <>
          <Alert error={error} />
          {data.active_plan ? (
            <>
              <section
                className="panel planning-active"
                aria-labelledby="planning-active-title"
              >
                <div className="panel-heading">
                  <div>
                    <p className="eyebrow">PLANNING ACTIF</p>
                    <h2 id="planning-active-title">{data.active_plan.title}</h2>
                  </div>
                  <Link to={base + "/plannings/" + data.active_plan.id}>
                    Voir le planning ↗
                  </Link>
                </div>
                <PlanBadges plan={data.active_plan} />
                <p className="planning-muted">
                  {period(
                    data.active_plan.start_date,
                    data.active_plan.end_date,
                  )}{" "}
                  · {data.active_plan.done_count} /{" "}
                  {plural(
                    data.active_plan.tasks_count,
                    "tâche terminée",
                    "tâches terminées",
                  )}{" "}
                  · {duration(data.active_plan.planned_minutes)} prévues
                </p>
              </section>
              <ProgressMetrics
                progress={data.progress}
                streak={data.streak_days}
              />
              <section
                className="panel"
                aria-labelledby="planning-today-title"
                aria-describedby="planning-today-date"
              >
                <div className="panel-heading">
                  <h2 id="planning-today-title">Aujourd’hui</h2>
                  <span id="planning-today-date" className="planning-muted">
                    {dayLabel(today())}
                  </span>
                </div>
                {data.today.length ? (
                  <ul className="planning-tasks">
                    {data.today.map((task) => {
                      const current = status.view(task),
                        saving = !!status.saving[task.id];
                      return (
                        <TaskItem key={task.id} task={current} saving={saving}>
                          <TaskStatusControls
                            task={current}
                            saving={saving}
                            onChange={(value) =>
                              void status.change(task, value)
                            }
                          />
                        </TaskItem>
                      );
                    })}
                  </ul>
                ) : (
                  <Empty title="Rien de prévu aujourd’hui">
                    Aucune tâche de révision n’est planifiée pour aujourd’hui.
                  </Empty>
                )}
              </section>
              <section className="panel" aria-labelledby="planning-week-title">
                <h2 id="planning-week-title">Les 7 prochains jours</h2>
                {upcoming.length ? (
                  <TaskDays
                    tasks={upcoming}
                    render={(task) => (
                      <TaskItem key={task.id} task={status.view(task)} />
                    )}
                  />
                ) : (
                  <Empty title="Aucune tâche à venir">
                    Les tâches des prochains jours de votre planning actif
                    apparaîtront ici.
                  </Empty>
                )}
              </section>
            </>
          ) : (
            <section className="panel planning-start">
              <Empty headingLevel={2} title="Aucun planning actif">
                Générez un programme à partir de vos objectifs, de vos échéances
                et de vos disponibilités, puis activez-le pour suivre vos tâches
                au quotidien.
              </Empty>
              <p className="planning-center">
                <Link className="btn_one" to={base + "/plannings"}>
                  Générer un planning ↗
                </Link>
              </p>
            </section>
          )}
          <div className="planning-columns">
            <section
              className="panel"
              aria-labelledby="planning-deadlines-title"
            >
              <div className="panel-heading">
                <h2 id="planning-deadlines-title">Prochaines échéances</h2>
                <Link to={base + "/objectifs"}>Gérer mes échéances ↗</Link>
              </div>
              {data.next_deadlines.length ? (
                <ul className="planning-deadlines">
                  {data.next_deadlines.map((deadline) => (
                    <li key={deadline.id}>
                      <span className="ti-flag" aria-hidden="true" />
                      <div>
                        <p className="planning-item-title">{deadline.title}</p>
                        <p className="planning-muted">
                          {deadline.kind_label} · {date(deadline.due_at)}
                          {deadline.goal && ` · ${deadline.goal.title}`}
                        </p>
                      </div>
                    </li>
                  ))}
                </ul>
              ) : (
                <Empty title="Aucune échéance à venir">
                  Ajoutez vos examens, quiz et devoirs pour que vos plannings en
                  tiennent compte.
                </Empty>
              )}
            </section>
            <section className="panel" aria-labelledby="planning-goals-title">
              <div className="panel-heading">
                <h2 id="planning-goals-title">Avancement par objectif</h2>
                <Link to={base + "/objectifs"}>Gérer mes objectifs ↗</Link>
              </div>
              {data.goals.length ? (
                <GoalProgress goals={data.goals} />
              ) : (
                <Empty title="Aucun objectif en cours">
                  Fixez un premier objectif de révision pour suivre votre
                  avancement.
                </Empty>
              )}
            </section>
          </div>
        </>
      )}
    </div>
  );
}
