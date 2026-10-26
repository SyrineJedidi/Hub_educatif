import { t, n } from "./i18n";
import { useEffect, useState } from "react";
import { api, date } from "../api/client";
import { useResource } from "../hooks/useResource";
import {
  Alert,
  Empty,
  Form,
  Loading,
  Pagination,
  Select,
  Textarea,
} from "../components/UI";
import { useFormValidation } from "./useFormValidation";
const ratings = {
  TOO_EASY: "Trop facile",
  SUITABLE: "Adapté",
  TOO_HARD: "Trop difficile",
};
interface FeedbackData {
  id: string;
  rating: keyof typeof ratings;
  comment: string;
  updated_at: string;
}

export function StudentFeedback({ quizId }: { quizId: string }) {
  const { data, error, loading } = useResource<{
    feedback: FeedbackData | null;
  }>(`student/quizzes/${quizId}/feedback/`);
  const [rating, setRating] = useState(""),
    [comment, setComment] = useState("");
  useEffect(() => {
    if (data) {
      setRating(data.feedback?.rating || "");
      setComment(data.feedback?.comment || "");
    }
  }, [data]);
  const validation = useFormValidation(
    () => {
      const errors: Record<string, string> = {};
      if (!(rating in ratings))
        errors.rating = t("Choisissez une appréciation.");
      if (Array.from(comment.trim()).length > 1000)
        errors.comment = t("Limitez le commentaire à 1 000 caractères.");
      return errors;
    },
    { rating, comment },
  );
  return (
    <section className="panel quiz-feedback-panel">
      <h2>{t("Votre retour sur ce quiz")}</h2>
      <p>
        {t(
          "Facultatif, un seul retour par étudiant et quiz. Vous pouvez le modifier ; il ne change pas votre score.",
        )}
      </p>
      {loading ? (
        <Loading />
      ) : error ? (
        <Alert error={error} />
      ) : (
        <Form
          {...validation.formProps}
          label={t("Enregistrer mon retour")}
          onSubmit={async () => {
            validation.check();
            try {
              await api(`student/quizzes/${quizId}/feedback/`, "PUT", {
                rating,
                comment,
              });
            } catch (error) {
              validation.serverErrors(error);
              throw error;
            }
          }}
        >
          <Select
            label={t("Appréciation")}
            name="rating"
            required
            value={rating}
            onChange={(e) => setRating(e.target.value)}
            error={validation.errors.rating}
          >
            <option value="">{t("Choisir une appréciation")}</option>
            {Object.entries(ratings).map(([key, label]) => (
              <option key={key} value={key}>
                {t(label)}
              </option>
            ))}
          </Select>
          <Textarea
            label={t("Commentaire (facultatif)")}
            name="comment"
            rows={4}
            maxLength={1000}
            value={comment}
            onChange={(e) => setComment(e.target.value)}
            error={validation.errors.comment}
          />
        </Form>
      )}
    </section>
  );
}
export function ManagerFeedback({ quizId }: { quizId: string }) {
  const [page, setPage] = useState(1);
  const { data, error, loading } = useResource<{
    count: number;
    distribution: Record<string, number>;
    results: (FeedbackData & {
      student: { first_name: string; last_name: string };
    })[];
  }>(`quizzes/${quizId}/feedback/?page=${page}`);
  useEffect(() => setPage(1), [quizId]);
  return (
    <section className="panel quiz-feedback-panel">
      <h2>{t("Retours des étudiants")}</h2>
      {loading ? (
        <Loading />
      ) : error ? (
        <Alert error={error} />
      ) : data ? (
        <>
          <dl className="quiz-facts">
            {Object.entries(ratings).map(([key, label]) => (
              <div key={key}>
                <dt>{t(label)}</dt>
                <dd>{n(data.distribution[key])}</dd>
              </div>
            ))}
          </dl>
          {data.count ? (
            data.results.map((value) => (
              <article className="quiz-feedback" key={value.id}>
                <h3>
                  <bdi>
                    {value.student.first_name} {value.student.last_name}
                  </bdi>{" "}
                  · {t(ratings[value.rating])}
                </h3>
                <p>{date(value.updated_at)}</p>
                <p dir="auto" style={{ whiteSpace: "pre-wrap" }}>
                  {value.comment || t("Sans commentaire.")}
                </p>
              </article>
            ))
          ) : (
            <Empty>{t("Aucun retour pour ce quiz.")}</Empty>
          )}
          <Pagination page={page} count={data.count} onChange={setPage} />
        </>
      ) : null}
    </section>
  );
}
