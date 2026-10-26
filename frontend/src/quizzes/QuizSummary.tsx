import { Badge } from "../components/UI";
import type { Quiz } from "./types";
import { levels, quizStatuses, quizVisibility } from "./types";
import { useQuizContext } from "./useQuizContext";
export default function QuizSummary({ quiz }: { quiz: Quiz }) {
  const { student } = useQuizContext();
  return (
    <>
      <div className="quiz-badges">
        <Badge>{quizStatuses[quiz.status]}</Badge>
        <Badge>{levels[quiz.level]}</Badge>
      </div>
      <dl className="quiz-facts">
        <div>
          <dt>Groupe</dt>
          <dd>{quiz.learning_group_name}</dd>
        </div>
        <div>
          <dt>Questions</dt>
          <dd>{quiz.question_count}</dd>
        </div>
        <div>
          <dt>Total des points</dt>
          <dd>{quiz.total_points}</dd>
        </div>
        <div>
          <dt>Durée</dt>
          <dd>
            {quiz.duration_minutes === null
              ? "Illimitée"
              : quiz.duration_minutes + " min"}
          </dd>
        </div>
        <div>
          <dt>Tentatives autorisées</dt>
          <dd>{quiz.max_attempts}</dd>
        </div>
        {quiz.teacher_name && (
          <div>
            <dt>Enseignant</dt>
            <dd>{quiz.teacher_name}</dd>
          </div>
        )}
      </dl>
      {!student && (
        <p className="field-help">
          <strong>Visibilité : </strong>
          {quizVisibility[quiz.status]}
        </p>
      )}
    </>
  );
}
