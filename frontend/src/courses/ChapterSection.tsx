import { useEffect, useId, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import {
  Alert,
  Badge,
  Field,
  Form,
  Modal,
  Select,
  Textarea,
} from "../components/UI";
import { useFormValidation } from "../quizzes/useFormValidation";
import type { Chapter, Progress, Resource } from "./types";
import { isProcessing, kindIcons } from "./types";
import { percent, plural, resourceFacts } from "./format";
import { useCourseContext } from "./useCourseContext";
import {
  DESCRIPTION_MAX_LENGTH,
  TITLE_MAX_LENGTH,
  validateChapter,
  validateResource,
} from "./validation";
import ResourceUpload from "./ResourceUpload";

export function CourseProgress({
  progress,
  label,
}: {
  progress?: Progress;
  label: string;
}) {
  const value = progress || { viewed: 0, total: 0, percent: 0 };
  return (
    <div className="course-progress">
      <progress
        aria-label={label}
        value={value.viewed}
        max={Math.max(1, value.total)}
      />
      <p>
        {value.viewed}/{value.total} ressources consultées
        {value.total ? " · " + percent(value.percent) : ""}
      </p>
    </div>
  );
}

// Same fragment as the chapter links returned by the search API.
export const chapterAnchor = (id: string) => "chapitre-" + id;

// Moving an item re-renders the list; focus follows the item that moved.
export function useMoveFocus() {
  const pending = useRef<{ id: string; up: boolean } | null>(null);
  useEffect(() => {
    if (!pending.current) return;
    const { id, up } = pending.current;
    pending.current = null;
    const first = document.getElementById(id + (up ? "-up" : "-down"));
    const other = document.getElementById(id + (up ? "-down" : "-up"));
    const target =
      first instanceof HTMLButtonElement && !first.disabled ? first : other;
    target?.focus();
  });
  return (id: string, up: boolean) => {
    pending.current = { id, up };
  };
}

export function ChapterForm({
  courseId,
  chapter,
  onSaved,
}: {
  courseId: string;
  chapter?: Chapter;
  onSaved: () => void;
}) {
  const [title, setTitle] = useState(chapter?.title || ""),
    [description, setDescription] = useState(chapter?.description || "");
  const validation = useFormValidation(
    () => validateChapter({ title, description }),
    { title, description },
  );
  async function submit() {
    validation.check();
    try {
      await api(
        "courses/" +
          courseId +
          "/chapters/" +
          (chapter ? chapter.id + "/" : ""),
        chapter ? "PATCH" : "POST",
        { title: title.trim(), description: description.trim() },
      );
    } catch (e) {
      validation.serverErrors(e);
      throw e;
    }
  }
  return (
    <Form
      {...validation.formProps}
      label={chapter ? "Enregistrer le chapitre" : "Ajouter le chapitre"}
      onSubmit={submit}
      onSuccess={onSaved}
    >
      <Field
        label="Titre du chapitre"
        name="title"
        value={title}
        required
        maxLength={TITLE_MAX_LENGTH}
        onChange={(e) => setTitle(e.target.value)}
        error={validation.errors.title}
      />
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

function ResourceForm({
  courseId,
  resource,
  chapters,
  onSaved,
}: {
  courseId: string;
  resource: Resource;
  chapters: Chapter[];
  onSaved: () => void;
}) {
  const [title, setTitle] = useState(resource.title),
    [description, setDescription] = useState(resource.description),
    [chapter, setChapter] = useState(resource.chapter_id);
  const validation = useFormValidation(
    () =>
      validateResource(
        { title, description, chapter },
        chapters.map((c) => c.id),
      ),
    { title, description, chapter_id: chapter },
  );
  async function submit() {
    validation.check();
    try {
      await api(
        "courses/" + courseId + "/resources/" + resource.id + "/",
        "PATCH",
        {
          title: title.trim(),
          description: description.trim(),
          // A move appends the resource to the target chapter, so only send a real change.
          ...(chapter !== resource.chapter_id ? { chapter_id: chapter } : {}),
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
      label="Enregistrer la ressource"
      onSubmit={submit}
      onSuccess={onSaved}
    >
      <Field
        label="Titre de la ressource"
        name="title"
        value={title}
        required
        maxLength={TITLE_MAX_LENGTH}
        onChange={(e) => setTitle(e.target.value)}
        error={validation.errors.title}
      />
      <Textarea
        label="Description (facultative)"
        name="description"
        rows={3}
        value={description}
        maxLength={DESCRIPTION_MAX_LENGTH}
        onChange={(e) => setDescription(e.target.value)}
        error={validation.errors.description}
      />
      <Select
        label="Chapitre"
        name="chapter_id"
        value={chapter}
        required
        onChange={(e) => setChapter(e.target.value)}
        error={validation.errors.chapter_id}
      >
        {chapters.map((c, i) => (
          <option key={c.id} value={c.id}>
            Chapitre {i + 1} · {c.title}
          </option>
        ))}
      </Select>
      <p className="field-help">
        Une ressource déplacée est ajoutée à la fin du chapitre choisi.
      </p>
    </Form>
  );
}

export interface ChapterManagement {
  count: number;
  chapters: Chapter[];
  editable: boolean;
  busy: boolean;
  onMove: (offset: number) => void;
  onChanged: () => void;
  onResources: (chapterId: string, resources: Resource[]) => void;
  announce: (message: string) => void;
}
export default function ChapterSection(props: {
  courseId: string;
  chapter: Chapter;
  index: number;
  manager?: ChapterManagement;
}) {
  return props.manager ? (
    <ManagedChapter {...props} manager={props.manager} />
  ) : (
    <StudentChapter {...props} />
  );
}

function StudentChapter({
  courseId,
  chapter,
  index,
}: {
  courseId: string;
  chapter: Chapter;
  index: number;
}) {
  const { base } = useCourseContext();
  const heading = useId();
  return (
    <section
      id={chapterAnchor(chapter.id)}
      className="panel course-chapter"
      aria-labelledby={heading}
      tabIndex={-1}
    >
      <p className="eyebrow">CHAPITRE {index + 1}</p>
      <h3 id={heading}>{chapter.title}</h3>
      {chapter.description && (
        <p className="course-description">{chapter.description}</p>
      )}
      {chapter.resources.length ? (
        <ul className="course-resource-list">
          {chapter.resources.map((resource) => (
            <li className="course-resource-item" key={resource.id}>
              <span
                className={kindIcons[resource.kind] + " course-kind-icon"}
                aria-hidden="true"
              />
              <div>
                <p className="course-resource-title">
                  <Link
                    to={base + "/" + courseId + "/ressources/" + resource.id}
                  >
                    {resource.title}
                  </Link>
                </p>
                <p className="course-muted">
                  {resource.kind_label} · {resourceFacts(resource)}
                </p>
                {resource.description && (
                  <p className="course-resource-description">
                    {resource.description}
                  </p>
                )}
              </div>
              {resource.viewed && <Badge>Consulté</Badge>}
            </li>
          ))}
        </ul>
      ) : (
        <p className="course-muted">
          Aucune ressource dans ce chapitre pour le moment.
        </p>
      )}
    </section>
  );
}

type ChapterModal =
  | { kind: "chapter-edit" }
  | { kind: "chapter-delete" }
  | { kind: "resource-edit"; resource: Resource }
  | { kind: "resource-delete"; resource: Resource };
function ManagedChapter({
  courseId,
  chapter,
  index,
  manager,
}: {
  courseId: string;
  chapter: Chapter;
  index: number;
  manager: ChapterManagement;
}) {
  const { base } = useCourseContext();
  const heading = useId();
  const [modal, setModal] = useState<ChapterModal | null>(null),
    [actionError, setActionError] = useState<unknown>(),
    [busy, setBusy] = useState(false);
  const locked = useRef(false),
    focusMove = useMoveFocus();
  const number = index + 1,
    resources = chapter.resources,
    blocked = busy || manager.busy;
  const chapterId = "course-chapter-" + chapter.id;
  const resourceName = (i: number) =>
    ` la ressource ${i + 1} du chapitre ${number}`;
  async function guarded(action: () => Promise<void>) {
    if (locked.current) return;
    locked.current = true;
    setBusy(true);
    setActionError(undefined);
    try {
      await action();
    } catch (e) {
      setActionError(e);
    } finally {
      locked.current = false;
      setBusy(false);
    }
  }
  function move(i: number, offset: number) {
    const target = i + offset;
    if (target < 0 || target >= resources.length) return;
    void guarded(async () => {
      const ids = resources.map((r) => r.id);
      [ids[i], ids[target]] = [ids[target], ids[i]];
      const result = await api<{ results: Resource[] }>(
        "courses/" +
          courseId +
          "/chapters/" +
          chapter.id +
          "/resources/reorder/",
        "POST",
        { resource_ids: ids },
      );
      focusMove("course-resource-" + resources[i].id, offset < 0);
      manager.onResources(chapter.id, result.results);
      manager.announce(
        `Ressource « ${resources[i].title} » déplacée en position ${target + 1}.`,
      );
    });
  }
  function reprocess(resource: Resource) {
    void guarded(async () => {
      await api(
        "courses/" + courseId + "/resources/" + resource.id + "/reprocess/",
        "POST",
        {},
      );
      manager.announce(`Traitement relancé pour « ${resource.title} ».`);
      manager.onChanged();
    });
  }
  function closeAndRefresh(message: string) {
    setModal(null);
    manager.announce(message);
    manager.onChanged();
  }
  return (
    <section
      id={chapterAnchor(chapter.id)}
      className="panel course-chapter"
      aria-labelledby={heading}
      tabIndex={-1}
    >
      <div className="course-chapter-heading">
        <div>
          <p className="eyebrow">CHAPITRE {number}</p>
          <h3 id={heading}>{chapter.title}</h3>
        </div>
        {manager.editable && (
          <div className="actions course-chapter-tools">
            <button
              className="text-button"
              onClick={() => setModal({ kind: "chapter-edit" })}
            >
              Modifier
              <span className="visually-hidden"> le chapitre {number}</span>
            </button>
            <button
              id={chapterId + "-up"}
              className="course-order-button"
              disabled={index === 0}
              aria-disabled={manager.busy || undefined}
              onClick={() => manager.onMove(-1)}
            >
              <span aria-hidden="true">↑ </span>Monter
              <span className="visually-hidden"> le chapitre {number}</span>
            </button>
            <button
              id={chapterId + "-down"}
              className="course-order-button"
              disabled={index === manager.count - 1}
              aria-disabled={manager.busy || undefined}
              onClick={() => manager.onMove(1)}
            >
              <span aria-hidden="true">↓ </span>Descendre
              <span className="visually-hidden"> le chapitre {number}</span>
            </button>
            <button
              className="text-button"
              onClick={() => setModal({ kind: "chapter-delete" })}
            >
              Supprimer
              <span className="visually-hidden"> le chapitre {number}</span>
            </button>
          </div>
        )}
      </div>
      {chapter.description && (
        <p className="course-description">{chapter.description}</p>
      )}
      <Alert error={actionError} />
      {resources.length ? (
        <div
          className="table-scroll course-table-scroll"
          role="region"
          aria-label={"Ressources du chapitre " + number}
          tabIndex={0}
        >
          <table className="course-table course-resource-table">
            <caption className="visually-hidden">
              Ressources du chapitre {number} : {chapter.title}
            </caption>
            <thead>
              <tr>
                <th scope="col">Type</th>
                <th scope="col">Ressource</th>
                <th scope="col">Traitement</th>
                <th scope="col">Fichier</th>
                <th scope="col">Actions</th>
              </tr>
            </thead>
            <tbody>
              {resources.map((resource, i) => {
                const id = "course-resource-" + resource.id;
                return (
                  <tr key={resource.id}>
                    <td>
                      <span className="course-kind">
                        <span
                          className={
                            kindIcons[resource.kind] + " course-kind-icon"
                          }
                          aria-hidden="true"
                        />
                        {resource.kind_label}
                      </span>
                    </td>
                    <th scope="row">
                      <Link
                        to={
                          base + "/" + courseId + "/ressources/" + resource.id
                        }
                      >
                        {resource.title}
                      </Link>
                      {resource.description && (
                        <small>{resource.description}</small>
                      )}
                    </th>
                    <td>
                      <Badge>{resource.processing_label}</Badge>
                      {isProcessing(resource) && (
                        <small className="course-processing">
                          <span className="ti-reload" aria-hidden="true" />{" "}
                          Actualisation automatique
                        </small>
                      )}
                      {resource.processing_status === "FAILED" &&
                        resource.processing_error && (
                          <small className="course-error-text">
                            {resource.processing_error}
                          </small>
                        )}
                    </td>
                    <td>
                      {resourceFacts(resource)}
                      <small>{resource.original_name}</small>
                    </td>
                    <td>
                      {manager.editable ? (
                        <div className="course-row-actions">
                          <button
                            className="text-button"
                            onClick={() =>
                              setModal({ kind: "resource-edit", resource })
                            }
                          >
                            Modifier
                            <span className="visually-hidden">
                              {resourceName(i)}
                            </span>
                          </button>
                          <button
                            id={id + "-up"}
                            className="course-order-button"
                            disabled={i === 0}
                            aria-disabled={blocked || undefined}
                            onClick={() => move(i, -1)}
                          >
                            <span aria-hidden="true">↑ </span>Monter
                            <span className="visually-hidden">
                              {resourceName(i)}
                            </span>
                          </button>
                          <button
                            id={id + "-down"}
                            className="course-order-button"
                            disabled={i === resources.length - 1}
                            aria-disabled={blocked || undefined}
                            onClick={() => move(i, 1)}
                          >
                            <span aria-hidden="true">↓ </span>Descendre
                            <span className="visually-hidden">
                              {resourceName(i)}
                            </span>
                          </button>
                          {(resource.processing_status === "FAILED" ||
                            resource.processing_status === "NO_TEXT") && (
                            <button
                              className="text-button"
                              aria-disabled={blocked || undefined}
                              onClick={() => reprocess(resource)}
                            >
                              Relancer le traitement
                              <span className="visually-hidden">
                                {" de" + resourceName(i)}
                              </span>
                            </button>
                          )}
                          <button
                            className="text-button"
                            onClick={() =>
                              setModal({ kind: "resource-delete", resource })
                            }
                          >
                            Supprimer
                            <span className="visually-hidden">
                              {resourceName(i)}
                            </span>
                          </button>
                        </div>
                      ) : (
                        <Link
                          className="text-button"
                          to={
                            base + "/" + courseId + "/ressources/" + resource.id
                          }
                        >
                          Consulter
                          <span className="visually-hidden">
                            {resourceName(i)}
                          </span>
                        </Link>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      ) : (
        <p className="course-muted">
          Aucune ressource dans ce chapitre pour le moment.
        </p>
      )}
      {manager.editable && (
        <ResourceUpload
          courseId={courseId}
          chapter={chapter}
          number={number}
          onUploaded={manager.onChanged}
        />
      )}
      {modal?.kind === "chapter-edit" && (
        <Modal
          title={"Modifier le chapitre " + number}
          onClose={() => setModal(null)}
        >
          <ChapterForm
            courseId={courseId}
            chapter={chapter}
            onSaved={() => closeAndRefresh("Chapitre enregistré.")}
          />
        </Modal>
      )}
      {modal?.kind === "chapter-delete" && (
        <Modal
          title={"Supprimer le chapitre " + number + " ?"}
          onClose={() => setModal(null)}
        >
          {resources.length ? (
            <>
              <p className="intro">
                Ce chapitre contient encore{" "}
                {plural(resources.length, "ressource", "ressources")}.
                Supprimez-les ou déplacez-les d’abord vers un autre chapitre.
              </p>
              <button className="btn_one" onClick={() => setModal(null)}>
                Revenir au cours
              </button>
            </>
          ) : (
            <>
              <p className="intro">
                Le chapitre « {chapter.title} » sera supprimé. Les autres
                chapitres seront renumérotés.
              </p>
              <Form
                label="Confirmer la suppression"
                onSubmit={() =>
                  api(
                    "courses/" + courseId + "/chapters/" + chapter.id + "/",
                    "DELETE",
                  )
                }
                onSuccess={() => closeAndRefresh("Chapitre supprimé.")}
              />
            </>
          )}
        </Modal>
      )}
      {modal?.kind === "resource-edit" && (
        <Modal title="Modifier la ressource" onClose={() => setModal(null)}>
          <ResourceForm
            courseId={courseId}
            resource={modal.resource}
            chapters={manager.chapters}
            onSaved={() => closeAndRefresh("Ressource enregistrée.")}
          />
        </Modal>
      )}
      {modal?.kind === "resource-delete" && (
        <Modal
          title={"Supprimer « " + modal.resource.title + " » ?"}
          onClose={() => setModal(null)}
        >
          <p className="intro">
            Le fichier, son texte extrait ou sa transcription et l’historique de
            consultation des étudiants pour cette ressource seront supprimés.
            Cette action est définitive.
          </p>
          <Form
            label="Confirmer la suppression"
            onSubmit={() =>
              api(
                "courses/" + courseId + "/resources/" + modal.resource.id + "/",
                "DELETE",
              )
            }
            onSuccess={() => closeAndRefresh("Ressource supprimée.")}
          />
        </Modal>
      )}
    </section>
  );
}
