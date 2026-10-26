import { t, LanguageNotice } from "./i18n";
import { useParams } from "react-router-dom";
import { useResource } from "../hooks/useResource";
import { Loading, Alert } from "../components/UI";
import type { Quiz } from "./types";
import QuizForm from "./QuizForm";
import "./quiz.css";
export default function QuizEditor({
  duplicate = false,
}: {
  duplicate?: boolean;
}) {
  const { id } = useParams();
  return (
    <div className="quiz-module">
      <LanguageNotice />
      <div className="page-heading">
        <div>
          <p className="eyebrow">{t("ATELIER PÉDAGOGIQUE")}</p>
          <h1>
            {duplicate
              ? t("Dupliquer le quiz")
              : id
                ? t("Modifier le brouillon")
                : t("Créer un quiz")}
          </h1>
          <p>
            {duplicate
              ? t(
                  "Reprenez les questions et leurs points dans un nouveau brouillon indépendant.",
                )
              : t(
                  "Préparez votre contenu ; la publication restera une action distincte.",
                )}
          </p>
        </div>
      </div>
      {id ? <ExistingEditor id={id} duplicate={duplicate} /> : <QuizForm />}
    </div>
  );
}
function ExistingEditor({ id, duplicate }: { id: string; duplicate: boolean }) {
  const { data, error, loading } = useResource<Quiz>("quizzes/" + id + "/");
  if (loading) return <Loading />;
  if (!data) return <Alert error={error} />;
  if (!duplicate && data.status !== "DRAFT")
    return (
      <Alert error="Ce quiz est verrouillé. Dupliquez-le pour préparer un nouveau brouillon." />
    );
  if (duplicate && data.status === "DRAFT")
    return (
      <Alert error="Ce quiz est déjà un brouillon. Vous pouvez le modifier directement." />
    );
  return <QuizForm key={data.id} quiz={data} duplicate={duplicate} />;
}
