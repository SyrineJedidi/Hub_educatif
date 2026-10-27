import { t, n } from "./i18n";
import { Badge } from "../components/UI";
import type { Quiz } from "./types";
import { levels, quizStatuses, quizVisibility } from "./types";
import { useQuizContext } from "./useQuizContext";
import { date } from "../api/client";
export default function QuizSummary({ quiz }: { quiz: Quiz }) {
  const { student } = useQuizContext();
  return (
    <>
      <div className="quiz-badges">
        <Badge>{t(quizStatuses[quiz.status])}</Badge>
        <Badge>{t(levels[quiz.level])}</Badge>
        {(quiz.opens_at || quiz.closes_at) && (
          <Badge>
            {quiz.availability?.state === "UPCOMING"
              ? t("À venir")
              : quiz.availability?.state === "CLOSED"
                ? t("Fermé")
                : t("Ouvert")}
          </Badge>
        )}
      </div>
      <dl className="quiz-facts">
        <div>
          <dt>{t("Groupe")}</dt>
          <dd>{quiz.learning_group_name}</dd>
        </div>
        <div>
          <dt>{t("Questions")}</dt>
          <dd>{n(quiz.question_count)}</dd>
        </div>
        <div>
          <dt>{t("Total des points")}</dt>
          <dd>{n(quiz.total_points)}</dd>
        </div>
        <div>
          <dt>{t("Durée")}</dt>
          <dd>
            {quiz.duration_minutes === null
              ? t("Illimitée")
              : n(quiz.duration_minutes) + t(" min")}
          </dd>
        </div>
        <div>
          <dt>{t("Tentatives autorisées")}</dt>
          <dd>{n(quiz.max_attempts)}</dd>
        </div>
        {quiz.teacher_name && (
          <div>
            <dt>{t("Enseignant")}</dt>
            <dd>{quiz.teacher_name}</dd>
          </div>
        )}
      </dl>
      {(quiz.opens_at || quiz.closes_at) && (
        <p className="field-help">
          {quiz.opens_at && (
            <>
              {t("Ouverture : ")}
              {date(quiz.opens_at)}.{" "}
            </>
          )}
          {quiz.closes_at && (
            <>
              {t("Fermeture : ")}
              {date(quiz.closes_at)}.{" "}
            </>
          )}
          {t(" Fuseau : Africa/Tunis (UTC+01:00).")}
        </p>
      )}
      {!student && (
        <p className="field-help">
          <strong>{t("Visibilité : ")}</strong>
          {t(quizVisibility[quiz.status])}
        </p>
      )}
    </>
  );
}
