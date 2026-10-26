import { t } from "./i18n";
import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api } from "../api/client";
import { Modal, Form } from "../components/UI";
import type { Quiz } from "./types";
import { useQuizContext } from "./useQuizContext";
export default function QuizActions({
  quiz,
  onDone,
}: {
  quiz: Quiz;
  onDone?: () => void;
}) {
  const { base, student } = useQuizContext(),
    navigate = useNavigate();
  const [action, setAction] = useState<"delete" | "archive" | null>(null);
  if (student) return null;
  return (
    <>
      <div className="actions quiz-actions">
        <Link className="text-button" to={base + "/" + quiz.id + "/resultats"}>
          {t("Résultats des étudiants ")}
        </Link>
        {quiz.status === "DRAFT" ? (
          <>
            <Link
              className="text-button"
              to={base + "/" + quiz.id + "/modifier"}
            >
              {t("Modifier le brouillon ")}
            </Link>
            <button className="text-button" onClick={() => setAction("delete")}>
              {t("Supprimer le brouillon ")}
            </button>
          </>
        ) : (
          <>
            <Link
              className="text-button"
              to={base + "/" + quiz.id + "/dupliquer"}
            >
              {t("Dupliquer en brouillon ")}
            </Link>
            {quiz.status === "PUBLISHED" && (
              <button
                className="text-button"
                onClick={() => setAction("archive")}
              >
                {t("Archiver ")}
              </button>
            )}
          </>
        )}
      </div>
      {action && (
        <Modal
          title={
            action === "delete"
              ? t("Supprimer ce brouillon ?")
              : t("Archiver ce quiz ?")
          }
          onClose={() => setAction(null)}
        >
          <p className="intro">
            {action === "delete"
              ? t(
                  "Le brouillon et toutes ses questions seront supprimés. Cette action est définitive.",
                )
              : t(
                  "Le quiz et ses questions seront conservés. Il ne sera plus visible aux étudiants.",
                )}
          </p>
          <Form
            label={
              action === "delete"
                ? t("Confirmer la suppression")
                : t("Confirmer l’archivage")
            }
            onSubmit={() =>
              api(
                "quizzes/" +
                  quiz.id +
                  "/" +
                  (action === "archive" ? "archive/" : ""),
                action === "archive" ? "POST" : "DELETE",
                action === "archive" ? {} : undefined,
              )
            }
            onSuccess={() => {
              const deleted = action === "delete";
              setAction(null);
              onDone?.();
              if (deleted) navigate(base, { replace: true });
            }}
          />
        </Modal>
      )}
    </>
  );
}
