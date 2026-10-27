import { t, n, LanguageNotice } from "./i18n";
import { Link } from "react-router-dom";
import { useResource } from "../hooks/useResource";
import { Alert, Empty, Loading } from "../components/UI";
import { date } from "../api/client";
import type { AttemptSummary } from "./attemptTypes";
import "./quiz.css";

interface Priority {
  quiz_id: string;
  quiz_title: string;
  opens_at: string | null;
  closes_at: string | null;
  deadline?: string | null;
  attempt_id?: string;
}
export interface ProgressData {
  priorities: {
    to_finish: Priority[];
    to_start: Priority[];
    upcoming: Priority[];
  };
  counts: Record<string, number>;
  completed_quizzes: number;
  remaining_quizzes: number;
  scored_quizzes: number;
  average_best_percentage: number | null;
  timeline: (AttemptSummary & { percentage: number })[];
}

export function Priorities({ data }: { data: ProgressData }) {
  return (
    <section className="panel quiz-priorities">
      <h2>{t("Mes quiz par priorité")}</h2>
      <div className="quiz-priority-grid">
        {(
          [
            ["to_finish", t("À terminer")],
            ["to_start", t("À commencer")],
            ["upcoming", t("À venir")],
          ] as const
        ).map(([key, label]) => (
          <section key={key}>
            <h3>
              {t(label)} · {n(data.counts[key])}
            </h3>
            {data.priorities[key].length ? (
              <ul>
                {data.priorities[key].map((item) => (
                  <li key={item.quiz_id}>
                    <h4 dir="auto">{item.quiz_title}</h4>
                    <p>
                      {key === "to_finish"
                        ? item.deadline
                          ? date(item.deadline)
                          : t("Sans échéance")
                        : key === "upcoming"
                          ? date(item.opens_at!)
                          : item.closes_at
                            ? date(item.closes_at)
                            : t("Sans échéance")}
                    </p>
                    <Link
                      className="text-button"
                      to={
                        key === "to_finish"
                          ? `/espace/tentatives/${item.attempt_id}`
                          : `/espace/quiz/${item.quiz_id}`
                      }
                    >
                      {key === "to_finish"
                        ? t("Reprendre")
                        : key === "upcoming"
                          ? t("Consulter")
                          : t("Commencer le quiz")}
                    </Link>
                  </li>
                ))}
              </ul>
            ) : (
              <p>{t("Aucun quiz dans cette catégorie.")}</p>
            )}
          </section>
        ))}
      </div>
      <p className="field-help">
        {t(
          "Les quiz archivés et les nouvelles tentatives facultatives ne comptent pas comme du travail obligatoire. Fuseau : Africa/Tunis (UTC+01:00).",
        )}
      </p>
    </section>
  );
}
export function QuizPriorities() {
  const { data, error, loading } = useResource<ProgressData>(
    "student/quiz-progress/",
  );
  return (
    <div className="quiz-module">
      <LanguageNotice />
      {loading ? (
        <Loading />
      ) : data ? (
        <Priorities data={data} />
      ) : (
        <Alert error={error} />
      )}
    </div>
  );
}
export function ProgressSummary() {
  const { data, error, loading } = useResource<ProgressData>(
    "student/quiz-progress/",
  );
  if (loading) return <Loading />;
  if (!data) return <Alert error={error} />;
  const timeline = data.timeline;
  return (
    <>
      <section className="panel quiz-progress-summary">
        <h2>{t("Tableau de progression")}</h2>
        <dl className="quiz-facts">
          <div>
            <dt>{t("Quiz distincts terminés")}</dt>
            <dd>{n(data.completed_quizzes)}</dd>
          </div>
          <div>
            <dt>{t("Quiz à commencer ou terminer")}</dt>
            <dd>{n(data.remaining_quizzes)}</dd>
          </div>
          <div>
            <dt>{t("Moyenne des meilleurs résultats")}</dt>
            <dd>
              {data.average_best_percentage === null
                ? t("Non disponible")
                : `${n(data.average_best_percentage)} %`}
            </dd>
          </div>
        </dl>
        <p>
          {t(
            "La moyenne retient le meilleur pourcentage corrigé de chaque quiz terminé, puis fait la moyenne de ces pourcentages. Seules les tentatives soumises ou expirées et corrigées entrent dans les scores.",
          )}
        </p>
        <p className="notice">
          {t(
            "Des quiz de difficultés différentes ne constituent pas une mesure exacte de maîtrise.",
          )}
        </p>
        {timeline.length ? (
          <>
            <h3>{t("Évolution des résultats corrigés")}</h3>
            <svg
              className="quiz-progress-chart"
              viewBox="0 0 640 200"
              role="img"
              aria-label={t(
                "Évolution chronologique des pourcentages, détaillée dans le tableau suivant",
              )}
            >
              {[0, 50, 100].map((score) => (
                <g key={score}>
                  <line
                    x1="38"
                    y1={170 - score * 1.5}
                    x2="620"
                    y2={170 - score * 1.5}
                    stroke="#cbd0e6"
                  />
                  <text x="0" y={175 - score * 1.5} fontSize="12">
                    {n(score)}%
                  </text>
                </g>
              ))}
              <polyline
                fill="none"
                stroke="#554eea"
                strokeWidth="3"
                points={timeline
                  .map(
                    (row, index) =>
                      `${40 + (index * 570) / Math.max(1, timeline.length - 1)},${170 - row.percentage * 1.5}`,
                  )
                  .join(" ")}
              />
              {timeline.map((row, index) => (
                <circle
                  key={row.id}
                  cx={40 + (index * 570) / Math.max(1, timeline.length - 1)}
                  cy={170 - row.percentage * 1.5}
                  r="4"
                  fill="#554eea"
                >
                  <title>
                    {row.quiz_title} · {date(row.ended_at!)} ·{" "}
                    {n(row.percentage)}%
                  </title>
                </circle>
              ))}
            </svg>
            <div className="table-scroll" tabIndex={0}>
              <table>
                <caption>
                  {t("Historique chronologique des scores corrigés")}
                </caption>
                <thead>
                  <tr>
                    <th>{t("Date")}</th>
                    <th>{t("Quiz")}</th>
                    <th>{t("Tentative")}</th>
                    <th>{t("Pourcentage")}</th>
                  </tr>
                </thead>
                <tbody>
                  {timeline.map((row) => (
                    <tr key={row.id}>
                      <td>{date(row.ended_at!)}</td>
                      <td dir="auto">{row.quiz_title}</td>
                      <td>{n(row.number)}</td>
                      <td>{n(row.percentage)} %</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        ) : (
          <Empty>
            {t(
              "Aucun résultat corrigé pour le moment. Votre progression apparaîtra après une tentative terminée.",
            )}
          </Empty>
        )}
      </section>
      <Priorities data={data} />
    </>
  );
}
