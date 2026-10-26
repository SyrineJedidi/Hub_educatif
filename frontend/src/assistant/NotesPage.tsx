import { useEffect, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { allPages, date } from "../api/client";
import type { Group, Page } from "../api/types";
import { useResource } from "../hooks/useResource";
import {
  Alert,
  Empty,
  Field,
  Form,
  Loading,
  Modal,
  Pagination,
  Select,
  Textarea,
  val,
} from "../components/UI";
import { createNote, deleteNote, notesPath, updateNote } from "./api";
import { AssistantManagerNav } from "./AssistantRoutes";
import type { Note } from "./types";
import { personName, plural } from "./format";
import { useAssistantContext } from "./useAssistantContext";
import "./assistant.css";
const BODY_MAX = 20000;
function NoteForm({
  note,
  groups,
  group,
  onSaved,
}: {
  note: Note | null;
  groups: Group[];
  group: string;
  onSaved: (note: Note) => void;
}) {
  const [body, setBody] = useState(note?.body || "");
  const saved = useRef<Note | null>(null);
  return (
    <div className="assistant-note-form">
      <Form
        label={note ? "Enregistrer la note" : "Créer la note"}
        onSubmit={async (form) => {
          const title = val(form, "title").trim();
          saved.current = note
            ? await updateNote(note.id, { title, body })
            : await createNote({
                group_id: val(form, "group_id"),
                title,
                body,
              });
        }}
        onSuccess={() => saved.current && onSaved(saved.current)}
      >
        {note ? (
          <p className="field-help">
            Groupe : {note.group.name} ({note.group.code}) · version{" "}
            {note.version}
          </p>
        ) : (
          <Select
            label="Groupe pédagogique"
            name="group_id"
            required
            defaultValue={groups.some((g) => g.id === group) ? group : ""}
          >
            <option value="">Choisir un groupe</option>
            {groups.map((g) => (
              <option key={g.id} value={g.id}>
                {g.name} · {g.code}
              </option>
            ))}
          </Select>
        )}
        <Field
          label="Titre"
          name="title"
          required
          maxLength={120}
          defaultValue={note?.title || ""}
        />
        <Textarea
          label="Contenu de la note"
          name="body"
          required
          rows={14}
          maxLength={BODY_MAX}
          value={body}
          onChange={(e) => setBody(e.target.value)}
          aria-describedby="assistant-note-help"
        />
        <p id="assistant-note-help" className="field-help">
          {body.length.toLocaleString("fr-FR")} /{" "}
          {BODY_MAX.toLocaleString("fr-FR")} caractères. Séparez les notions par
          des paragraphes : l’assistant cite la note paragraphe par paragraphe.
        </p>
      </Form>
    </div>
  );
}
export default function NotesPage() {
  const { admin } = useAssistantContext();
  const [params, setParams] = useSearchParams();
  const group = params.get("group") || "",
    page = Math.max(1, Number(params.get("page")) || 1);
  const [groups, setGroups] = useState<Group[]>([]),
    [groupsError, setGroupsError] = useState<unknown>();
  useEffect(() => {
    let active = true;
    allPages<Group>("groups/")
      .then((items) => {
        if (active) setGroups(items);
      })
      .catch((e) => {
        if (active) setGroupsError(e);
      });
    return () => {
      active = false;
    };
  }, []);
  const notes = useResource<Page<Note>>(notesPath(group, page));
  const [editing, setEditing] = useState<Note | "new" | null>(null),
    [removing, setRemoving] = useState<Note | null>(null),
    [done, setDone] = useState("");
  const writable = groups.filter((g) => !g.archived);
  function filter(next: Record<string, string>) {
    setParams(
      (current) => {
        const result = new URLSearchParams(current);
        for (const [key, value] of Object.entries(next))
          if (value) result.set(key, value);
          else result.delete(key);
        return result;
      },
      { replace: true },
    );
  }
  return (
    <div className="assistant-module">
      <div className="page-heading">
        <div>
          <p className="eyebrow">ASSISTANT PÉDAGOGIQUE</p>
          <h1>Notes de cours</h1>
          <p>
            Rédigez les notes à partir desquelles l’assistant répond aux
            questions de vos groupes. Chaque modification est prise en compte
            dès la question suivante.
          </p>
        </div>
        <button
          className="btn_one"
          onClick={() => {
            setDone("");
            setEditing("new");
          }}
        >
          Rédiger une note +
        </button>
      </div>
      <AssistantManagerNav />
      <section className="panel" aria-label="Filtrer les notes">
        <div className="filters">
          <Select
            label="Groupe"
            value={group}
            onChange={(e) => filter({ group: e.target.value, page: "" })}
          >
            <option value="">
              {admin ? "Tous les groupes" : "Tous mes groupes"}
            </option>
            {groups.map((g) => (
              <option key={g.id} value={g.id}>
                {g.name} · {g.code}
                {g.archived ? " (archivé)" : ""}
              </option>
            ))}
          </Select>
        </div>
        <Alert error={groupsError} />
      </section>
      <Alert success={done} />
      {notes.loading && !notes.data ? (
        <Loading />
      ) : !notes.data ? (
        <section className="panel">
          <Alert error={notes.error} />
          <button className="text-button" onClick={notes.reload}>
            Réessayer le chargement
          </button>
        </section>
      ) : notes.data.results.length ? (
        <section className="panel">
          <div className="panel-heading">
            <h2>{plural(notes.data.count, "note", "notes")}</h2>
            <button className="text-button" onClick={notes.reload}>
              Actualiser la liste
            </button>
          </div>
          <Alert error={notes.error} />
          <div
            className="table-scroll"
            role="region"
            aria-label="Notes de cours"
            tabIndex={0}
          >
            <table className="assistant-table">
              <caption className="visually-hidden">
                Notes de cours utilisées par l’assistant
              </caption>
              <thead>
                <tr>
                  <th scope="col">Note</th>
                  <th scope="col">Groupe</th>
                  <th scope="col">Version</th>
                  <th scope="col">Mise à jour</th>
                  <th scope="col">Actions</th>
                </tr>
              </thead>
              <tbody>
                {notes.data.results.map((note) => (
                  <tr key={note.id}>
                    <th scope="row">
                      {note.title}
                      <small>
                        {plural(note.body.length, "caractère", "caractères")}
                        {admin && note.teacher
                          ? " · " + personName(note.teacher)
                          : ""}
                      </small>
                    </th>
                    <td>
                      {note.group.name}
                      <small>{note.group.code}</small>
                    </td>
                    <td>{note.version}</td>
                    <td>{date(note.updated_at)}</td>
                    <td>
                      <div className="assistant-row-actions">
                        <button
                          className="text-button"
                          onClick={() => {
                            setDone("");
                            setEditing(note);
                          }}
                        >
                          Modifier
                          <span className="visually-hidden">
                            {" "}
                            la note {note.title}
                          </span>
                        </button>
                        <button
                          className="text-button"
                          onClick={() => {
                            setDone("");
                            setRemoving(note);
                          }}
                        >
                          Supprimer
                          <span className="visually-hidden">
                            {" "}
                            la note {note.title}
                          </span>
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <Pagination
            page={page}
            count={notes.data.count}
            onChange={(p) => filter({ page: p > 1 ? String(p) : "" })}
          />
        </section>
      ) : (
        <section className="panel">
          <Empty headingLevel={2} title="Aucune note pour le moment">
            {group
              ? "Ce groupe n’a pas encore de note. Rédigez-en une pour que vos étudiants puissent interroger l’assistant."
              : "Rédigez une première note : l’assistant ne répond qu’à partir du contenu que vous partagez."}
          </Empty>
          <p className="assistant-empty-action">
            <button
              className="btn_one"
              onClick={() => {
                setDone("");
                setEditing("new");
              }}
            >
              Rédiger une note +
            </button>
          </p>
        </section>
      )}
      {editing && (
        <Modal
          title={
            editing === "new" ? "Nouvelle note de cours" : "Modifier la note"
          }
          onClose={() => setEditing(null)}
        >
          {editing === "new" && !writable.length ? (
            <p className="intro">
              Aucun groupe actif ne vous est confié : une note doit être
              rattachée à un groupe non archivé.
            </p>
          ) : (
            <NoteForm
              note={editing === "new" ? null : editing}
              groups={writable}
              group={group}
              onSaved={(note) => {
                setEditing(null);
                setDone(
                  editing === "new"
                    ? "Note « " + note.title + " » créée."
                    : "Note « " + note.title + " » enregistrée.",
                );
                notes.reload();
              }}
            />
          )}
        </Modal>
      )}
      {removing && (
        <Modal title="Supprimer cette note ?" onClose={() => setRemoving(null)}>
          <p className="intro">
            La note « {removing.title} » ne sera plus utilisée par l’assistant.
            Les réponses déjà données restent dans l’historique des étudiants.
          </p>
          <Form
            label="Confirmer la suppression"
            onSubmit={() => deleteNote(removing.id)}
            onSuccess={() => {
              setDone("Note « " + removing.title + " » supprimée.");
              setRemoving(null);
              notes.reload();
            }}
          />
        </Modal>
      )}
    </div>
  );
}
