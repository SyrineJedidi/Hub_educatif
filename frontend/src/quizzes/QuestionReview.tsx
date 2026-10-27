import { t, n } from "./i18n";
import type { Question } from "./types";
import { Badge } from "../components/UI";
export default function QuestionReview({
  question: q,
}: {
  question: Question;
}) {
  return (
    <>
      <div className="quiz-question-heading">
        <h3>
          {t("Question ")}
          {n(q.position)}
        </h3>
        <Badge>
          {n(q.points)}
          {t(q.points > 1 ? " points" : " point")}
        </Badge>
      </div>
      <p className="quiz-statement">{q.statement}</p>
      {q.notion && (
        <p className="field-help">
          {t("Notion : ")}
          {q.notion}
        </p>
      )}
      <ol className="quiz-choice-list">
        {(["a", "b", "c", "d"] as const).map((letter) => (
          <li
            className={
              q.correct_answer === letter.toUpperCase() ? "is-correct" : ""
            }
            key={letter}
          >
            <span className="quiz-letter">{letter.toUpperCase()}</span>
            <span>
              {
                q[
                  ("choice_" + letter) as
                    | "choice_a"
                    | "choice_b"
                    | "choice_c"
                    | "choice_d"
                ]
              }
            </span>
            {q.correct_answer === letter.toUpperCase() && (
              <Badge>{t("Bonne réponse")}</Badge>
            )}
          </li>
        ))}
      </ol>
      <div className="quiz-explanation">
        <h4>{t("Explication de correction")}</h4>
        <p>{q.explanation || t("À compléter avant publication.")}</p>
      </div>
    </>
  );
}
