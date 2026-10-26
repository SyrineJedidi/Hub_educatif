import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, ApiError } from "../api/client";
import { Form, Modal } from "../components/UI";
import type { Course } from "./types";
import { useCourseContext } from "./useCourseContext";
type Action = "publish" | "unpublish" | "archive" | "restore" | "delete";
const copy: Record<
  Action,
  { button: string; title: string; intro: string; confirm: string }
> = {
  publish: {
    button: "Publier le cours",
    title: "Publier ce cours ?",
    intro:
      "Les étudiants actuellement inscrits dans les groupes associés pourront consulter ses chapitres et ses ressources. Vous pourrez continuer à l’enrichir après publication.",
    confirm: "Confirmer la publication",
  },
  unpublish: {
    button: "Repasser en brouillon",
    title: "Retirer ce cours de la publication ?",
    intro:
      "Le cours redeviendra un brouillon et ne sera plus visible aux étudiants. Ses chapitres, ses ressources et l’historique de consultation sont conservés.",
    confirm: "Confirmer le retrait",
  },
  archive: {
    button: "Archiver",
    title: "Archiver ce cours ?",
    intro:
      "Le cours sera conservé en lecture seule et masqué aux étudiants. Vous pourrez le restaurer en brouillon.",
    confirm: "Confirmer l’archivage",
  },
  restore: {
    button: "Restaurer en brouillon",
    title: "Restaurer ce cours ?",
    intro:
      "Le cours redeviendra un brouillon modifiable, masqué aux étudiants jusqu’à sa prochaine publication.",
    confirm: "Confirmer la restauration",
  },
  delete: {
    button: "Supprimer le brouillon",
    title: "Supprimer ce brouillon ?",
    intro:
      "Le cours, ses chapitres, ses ressources et leurs fichiers seront supprimés. Cette action est définitive.",
    confirm: "Confirmer la suppression",
  },
};
export function publicationHints(course: Course) {
  const hints: string[] = [];
  if (!course.groups?.some((g) => !g.archived))
    hints.push("Associez au moins un groupe actif.");
  if (!course.chapters_count) hints.push("Ajoutez au moins un chapitre.");
  if (!course.resources_count) hints.push("Importez au moins une ressource.");
  return hints;
}
export default function CourseActions({
  course,
  onDone,
}: {
  course: Course;
  onDone: () => void;
}) {
  const { base, student } = useCourseContext(),
    navigate = useNavigate();
  const [action, setAction] = useState<Action | null>(null),
    [blockers, setBlockers] = useState<string[]>([]);
  if (student) return null;
  const actions: Action[] =
    course.status === "DRAFT"
      ? [
          "publish",
          "archive",
          ...(course.can_delete ? ["delete" as const] : []),
        ]
      : course.status === "PUBLISHED"
        ? ["unpublish", "archive"]
        : ["restore"];
  // The detail payload carries the server's own list (archived subject, inactive teacher…).
  const hints = course.publication_blockers ?? publicationHints(course);
  const shown = blockers.length ? blockers : hints;
  async function run(current: Action) {
    setBlockers([]);
    try {
      if (current === "delete")
        await api("courses/" + course.id + "/", "DELETE");
      else await api("courses/" + course.id + "/" + current + "/", "POST", {});
    } catch (e) {
      const reasons = e instanceof ApiError ? e.fields.publication : undefined;
      if (e instanceof ApiError && reasons) {
        setBlockers(Array.isArray(reasons) ? reasons : [reasons]);
        throw new ApiError(
          e.status,
          "Ce cours ne peut pas encore être publié : complétez les éléments indiqués.",
          {},
          e.code,
        );
      }
      throw e;
    }
  }
  return (
    <>
      <div className="actions course-actions">
        {actions.map((item) => (
          <button
            key={item}
            className={item === "publish" ? "btn_one" : "text-button"}
            onClick={() => {
              setBlockers([]);
              setAction(item);
            }}
          >
            {copy[item].button}
          </button>
        ))}
      </div>
      {action && (
        <Modal title={copy[action].title} onClose={() => setAction(null)}>
          <p className="intro">{copy[action].intro}</p>
          {action === "publish" && shown.length > 0 && (
            <div className="course-blockers">
              <h3>À compléter avant publication</h3>
              <ul>
                {shown.map((reason, i) => (
                  <li key={i}>{reason}</li>
                ))}
              </ul>
            </div>
          )}
          <Form
            label={copy[action].confirm}
            onSubmit={() => run(action)}
            onSuccess={() => {
              const deleted = action === "delete";
              setAction(null);
              if (deleted) navigate(base, { replace: true });
              else onDone();
            }}
          />
        </Modal>
      )}
    </>
  );
}
