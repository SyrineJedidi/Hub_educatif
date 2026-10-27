import { Link, useParams } from "react-router-dom";
import { ApiError, date } from "../api/client";
import { useResource } from "../hooks/useResource";
import { Alert, Empty, Loading } from "../components/UI";
import { usePlanningContext } from "./usePlanningContext";
import {
  PlanBadges,
  PriorityBadge,
  ProgressMetrics,
  TaskDays,
  TaskItem,
} from "./PlanningWidgets";
import { duration, fullName, paragraphs, period, plural } from "./format";
import type { CoachStudentDetail as Detail } from "./types";
import "./planning.css";
export default function CoachStudentDetail() {
  const { studentId } = useParams();
  const { coachApi, coachBase } = usePlanningContext();
  const { data, error, loading, reload } = useResource<Detail>(
    coachApi + studentId + "/",
  );
  const back = (
    <Link className="text-button" to={coachBase}>
      Tous les élèves ↗
    </Link>
  );
  if (loading && !data) return <Loading />;
  if (!data)
    return (
      <div className="planning-module">
        <div className="page-heading">
          <div>
            <p className="eyebrow">SUIVI DES RÉVISIONS</p>
            <h1>
              {error instanceof ApiError && error.status === 404
                ? "Élève introuvable"
                : "Suivi indisponible"}
            </h1>
          </div>
          {back}
        </div>
        <Alert error={error} />
        <button className="text-button" onClick={reload}>
          Réessayer le chargement
        </button>
      </div>
    );
  const plan = data.active_plan;
  return (
    <div className="planning-module">
      <div className="page-heading">
        <div>
          <p className="eyebrow">SUIVI DES RÉVISIONS · LECTURE SEULE</p>
          <h1>{fullName(data.student) || "Élève"}</h1>
          <p>
            {data.groups.length
              ? data.groups.map((group) => group.name).join(", ")
              : "Aucun groupe actuel"}
          </p>
        </div>
        {back}
      </div>
      <Alert error={error} />
      <ProgressMetrics progress={data.progress} streak={data.streak_days} />
      <div className="planning-columns">
        <section className="panel" aria-labelledby="planning-coach-goals">
          <h2 id="planning-coach-goals">Objectifs</h2>
          {data.goals.length ? (
            <div
              className="table-scroll"
              role="region"
              aria-label="Objectifs de l’élève"
              tabIndex={0}
            >
              <table className="planning-table planning-compact-table">
                <thead>
                  <tr>
                    <th scope="col">Objectif</th>
                    <th scope="col">Priorité</th>
                    <th scope="col">Statut</th>
                    <th scope="col">Réalisé / prévu</th>
                  </tr>
                </thead>
                <tbody>
                  {data.goals.map((goal) => (
                    <tr key={goal.id}>
                      <th scope="row">{goal.title}</th>
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
                          {goal.status_label}
                        </span>
                      </td>
                      <td>
                        {duration(goal.done_minutes)} /{" "}
                        {duration(goal.planned_minutes)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <Empty title="Aucun objectif">
              Cet élève n’a pas encore fixé d’objectif de révision.
            </Empty>
          )}
        </section>
        <section className="panel" aria-labelledby="planning-coach-deadlines">
          <h2 id="planning-coach-deadlines">Échéances à venir</h2>
          {data.deadlines.length ? (
            <ul className="planning-deadlines">
              {data.deadlines.map((deadline) => (
                <li key={deadline.id}>
                  <span className="ti-flag" aria-hidden="true" />
                  <div>
                    <p className="planning-item-title">{deadline.title}</p>
                    <p className="planning-muted">
                      {deadline.kind_label} · {date(deadline.due_at)}
                    </p>
                  </div>
                </li>
              ))}
            </ul>
          ) : (
            <Empty title="Aucune échéance à venir">
              Aucun examen, quiz ou devoir n’est noté pour le moment.
            </Empty>
          )}
        </section>
      </div>
      <section className="panel" aria-labelledby="planning-coach-plan">
        <h2 id="planning-coach-plan">
          {plan ? `Planning actif : ${plan.title}` : "Planning actif"}
        </h2>
        {plan ? (
          <>
            <PlanBadges plan={plan} />
            <p className="planning-muted">
              {period(plan.start_date, plan.end_date)} · {plan.done_count} /{" "}
              {plural(plan.tasks_count, "tâche terminée", "tâches terminées")} ·{" "}
              {duration(plan.planned_minutes)} prévues
            </p>
            {plan.advice && (
              <div className="planning-advice-text">
                <h3>Conseils du planning</h3>
                {paragraphs(plan.advice).map((text, index) => (
                  <p key={index}>{text}</p>
                ))}
              </div>
            )}
            {plan.tasks.length ? (
              <TaskDays
                tasks={plan.tasks}
                render={(task) => <TaskItem key={task.id} task={task} />}
              />
            ) : (
              <Empty title="Aucune tâche">
                Le planning actif ne contient aucune tâche.
              </Empty>
            )}
          </>
        ) : (
          <Empty title="Aucun planning actif">
            Cet élève n’a pas de planning de révision actif pour le moment.
          </Empty>
        )}
      </section>
    </div>
  );
}
