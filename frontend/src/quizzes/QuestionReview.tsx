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
        <h3>Question {q.position}</h3>
        <Badge>
          {q.points} point{q.points > 1 ? "s" : ""}
        </Badge>
      </div>
      <p className="quiz-statement">{q.statement}</p>
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
              <Badge>Bonne réponse</Badge>
            )}
          </li>
        ))}
      </ol>
      <div className="quiz-explanation">
        <h4>Explication de correction</h4>
        <p>{q.explanation || "À compléter avant publication."}</p>
      </div>
    </>
  );
}
