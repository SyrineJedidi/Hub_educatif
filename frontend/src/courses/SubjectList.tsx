import { useId, useState } from "react";
import { Link } from "react-router-dom";
import { api, query } from "../api/client";
import { useResource } from "../hooks/useResource";
import type { Page } from "../api/types";
import {
  Alert,
  Badge,
  Empty,
  Field,
  Form,
  Loading,
  Modal,
  Pagination,
  Select,
  Textarea,
} from "../components/UI";
import { useFormValidation } from "../quizzes/useFormValidation";
import type { Subject } from "./types";
import { personName, plural } from "./format";
import { useCourseContext } from "./useCourseContext";
import {
  DESCRIPTION_MAX_LENGTH,
  SUBJECT_NAME_MAX_LENGTH,
  validateSubject,
} from "./validation";
import "./courses.css";
function SubjectForm({
  subject,
  onSaved,
}: {
  subject?: Subject;
  onSaved: () => void;
}) {
  const help = useId();
  const [name, setName] = useState(subject?.name || ""),
    [code, setCode] = useState(subject?.code || ""),
    [description, setDescription] = useState(subject?.description || "");
  const validation = useFormValidation(
    () => validateSubject({ name, code, description }),
    { name, code, description },
  );
  async function submit() {
    validation.check();
    try {
      await api(
        subject ? "subjects/" + subject.id + "/" : "subjects/",
        subject ? "PATCH" : "POST",
        {
          name: name.trim(),
          code: code.trim().toUpperCase(),
          description: description.trim(),
        },
      );
    } catch (e) {
      validation.serverErrors(e);
      throw e;
    }
  }
  return (
    <Form
      {...validation.formProps}
      label={subject ? "Enregistrer la matière" : "Ajouter la matière"}
      onSubmit={submit}
      onSuccess={onSaved}
    >
      <Field
        label="Nom de la matière"
        name="name"
        value={name}
        required
        maxLength={SUBJECT_NAME_MAX_LENGTH}
        onChange={(e) => setName(e.target.value)}
        error={validation.errors.name}
      />
      <Field
        label="Code"
        name="code"
        value={code}
        required
        maxLength={20}
        autoCapitalize="characters"
        aria-describedby={help}
        onChange={(e) => setCode(e.target.value.toUpperCase())}
        error={validation.errors.code}
      />
      <p id={help} className="field-help">
        De 2 à 20 caractères : lettres, chiffres et tirets, par exemple
        MATH-101.
      </p>
      <Textarea
        label="Description (facultative)"
        name="description"
        rows={3}
        value={description}
        maxLength={DESCRIPTION_MAX_LENGTH}
        onChange={(e) => setDescription(e.target.value)}
        error={validation.errors.description}
      />
    </Form>
  );
}
type SubjectModal =
  | { kind: "create" }
  | { kind: "edit" | "archive" | "delete"; subject: Subject };
export default function SubjectList() {
  const { base } = useCourseContext();
  const [q, setQ] = useState(""),
    [archived, setArchived] = useState(""),
    [page, setPage] = useState(1),
    [modal, setModal] = useState<SubjectModal | null>(null),
    [notice, setNotice] = useState("");
  const { data, error, loading, reload } = useResource<Page<Subject>>(
    "subjects/?" + query({ q, archived, page }),
  );
  const filtered = !!(q || archived);
  function done(message: string) {
    setModal(null);
    setNotice(message);
    reload();
  }
  return (
    <div className="course-module">
      <div className="page-heading">
        <div>
          <p className="eyebrow">COURS ET RESSOURCES</p>
          <h1>Matières</h1>
          <p>
            Les matières regroupent les cours. Une matière archivée reste
            associée à ses cours mais ne peut plus être choisie pour un nouveau
            cours.
          </p>
        </div>
        <div className="course-heading-links">
          <button
            className="btn_one"
            onClick={() => {
              setNotice("");
              setModal({ kind: "create" });
            }}
          >
            Ajouter une matière +
          </button>
          <Link className="text-button" to={base}>
            Gestion des cours ↗
          </Link>
        </div>
      </div>
      <section
        className="panel course-filters"
        aria-label="Rechercher et filtrer les matières"
      >
        <div className="filters">
          <Field
            label="Rechercher une matière"
            type="search"
            placeholder="Nom ou code"
            value={q}
            maxLength={100}
            onChange={(e) => {
              setQ(e.target.value);
              setPage(1);
            }}
          />
          <Select
            label="Statut"
            value={archived}
            onChange={(e) => {
              setArchived(e.target.value);
              setPage(1);
            }}
          >
            <option value="">Toutes les matières</option>
            <option value="false">Actives</option>
            <option value="true">Archivées</option>
          </Select>
        </div>
        {filtered && (
          <button
            className="text-button"
            onClick={() => {
              setQ("");
              setArchived("");
              setPage(1);
            }}
          >
            Réinitialiser les filtres
          </button>
        )}
      </section>
      <Alert success={notice} />
      {loading ? (
        <Loading />
      ) : error || !data ? (
        <section className="panel">
          <Alert error={error} />
          <button className="text-button" onClick={reload}>
            Réessayer le chargement
          </button>
        </section>
      ) : data.results.length ? (
        <section className="panel">
          <div className="panel-heading">
            <h2>{plural(data.count, "matière", "matières")}</h2>
            <button className="text-button" onClick={reload}>
              Actualiser la liste
            </button>
          </div>
          <div
            className="table-scroll course-table-scroll"
            role="region"
            aria-label="Liste des matières"
            tabIndex={0}
          >
            <table className="course-table">
              <caption className="visually-hidden">Matières du Hub</caption>
              <thead>
                <tr>
                  <th scope="col">Code</th>
                  <th scope="col">Nom</th>
                  <th scope="col">Description</th>
                  <th scope="col">Cours</th>
                  <th scope="col">Statut</th>
                  <th scope="col">Actions</th>
                </tr>
              </thead>
              <tbody>
                {data.results.map((subject) => (
                  <tr key={subject.id}>
                    <td>
                      <code className="course-code">{subject.code}</code>
                    </td>
                    <th scope="row">
                      {subject.name}
                      <small>Créée par {personName(subject.created_by)}</small>
                    </th>
                    <td className="course-description-cell">
                      {subject.description || "—"}
                    </td>
                    <td>{subject.courses_count}</td>
                    <td>
                      <Badge>{subject.archived ? "Archivée" : "Active"}</Badge>
                    </td>
                    <td>
                      {subject.can_edit ? (
                        <div className="course-row-actions">
                          <button
                            className="text-button"
                            onClick={() => setModal({ kind: "edit", subject })}
                          >
                            Modifier
                            <span className="visually-hidden">
                              {" "}
                              la matière {subject.name}
                            </span>
                          </button>
                          <button
                            className="text-button"
                            onClick={() =>
                              setModal({ kind: "archive", subject })
                            }
                          >
                            {subject.archived ? "Réactiver" : "Archiver"}
                            <span className="visually-hidden">
                              {" "}
                              la matière {subject.name}
                            </span>
                          </button>
                          {subject.courses_count === 0 && (
                            <button
                              className="text-button"
                              onClick={() =>
                                setModal({ kind: "delete", subject })
                              }
                            >
                              Supprimer
                              <span className="visually-hidden">
                                {" "}
                                la matière {subject.name}
                              </span>
                            </button>
                          )}
                        </div>
                      ) : (
                        <span className="course-muted">Lecture seule</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <Pagination page={page} count={data.count} onChange={setPage} />
        </section>
      ) : (
        <section className="panel">
          <Empty
            headingLevel={2}
            title={
              filtered ? "Aucun résultat" : "Aucune matière pour le moment"
            }
          >
            {filtered
              ? "Aucune matière ne correspond à ces critères."
              : "Ajoutez une première matière pour pouvoir créer vos cours."}
          </Empty>
        </section>
      )}
      {modal?.kind === "create" && (
        <Modal title="Ajouter une matière" onClose={() => setModal(null)}>
          <SubjectForm onSaved={() => done("Matière ajoutée.")} />
        </Modal>
      )}
      {modal?.kind === "edit" && (
        <Modal title="Modifier la matière" onClose={() => setModal(null)}>
          <SubjectForm
            subject={modal.subject}
            onSaved={() => done("Matière enregistrée.")}
          />
        </Modal>
      )}
      {modal?.kind === "archive" && (
        <Modal
          title={
            (modal.subject.archived ? "Réactiver" : "Archiver") +
            " la matière « " +
            modal.subject.name +
            " » ?"
          }
          onClose={() => setModal(null)}
        >
          <p className="intro">
            {modal.subject.archived
              ? "La matière pourra de nouveau être choisie pour les cours."
              : "Les cours existants la conservent, mais elle ne pourra plus être choisie pour un nouveau cours."}
          </p>
          <Form
            label={
              modal.subject.archived
                ? "Confirmer la réactivation"
                : "Confirmer l’archivage"
            }
            onSubmit={() =>
              api("subjects/" + modal.subject.id + "/", "PATCH", {
                archived: !modal.subject.archived,
              })
            }
            onSuccess={() =>
              done(
                modal.subject.archived
                  ? "Matière réactivée."
                  : "Matière archivée.",
              )
            }
          />
        </Modal>
      )}
      {modal?.kind === "delete" && (
        <Modal
          title={"Supprimer la matière « " + modal.subject.name + " » ?"}
          onClose={() => setModal(null)}
        >
          <p className="intro">
            Cette matière n’est utilisée par aucun cours. Sa suppression est
            définitive.
          </p>
          <Form
            label="Confirmer la suppression"
            onSubmit={() => api("subjects/" + modal.subject.id + "/", "DELETE")}
            onSuccess={() => done("Matière supprimée.")}
          />
        </Modal>
      )}
    </div>
  );
}
