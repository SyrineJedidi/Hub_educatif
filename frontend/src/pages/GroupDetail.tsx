import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { api, allPages, date, iso, localDateTime, query } from "../api/client";
import type { Group, User, Page, Enrollment } from "../api/types";
import { useResource } from "../hooks/useResource";
import {
  Alert,
  Field,
  Select,
  Form,
  Modal,
  Loading,
  Empty,
  Badge,
  Pagination,
  val,
} from "../components/UI";
import GroupForm from "./GroupForm";
export default function GroupDetail() {
  const { id } = useParams(),
    { user } = useAuth();
  const admin = user!.role === "ADMIN";
  const group = useResource<Group>("groups/" + id + "/");
  const [page, setPage] = useState(1);
  const enrollments = useResource<Page<Enrollment>>(
    "enrollments/?" + query({ group: id!, page }),
  );
  const [edit, setEdit] = useState(false),
    [add, setAdd] = useState(false),
    [ending, setEnding] = useState<Enrollment | null>(null),
    [students, setStudents] = useState<User[]>([]),
    [error, setError] = useState<unknown>(),
    [deleting, setDeleting] = useState(false);
  useEffect(() => {
    if (add)
      allPages<User>("admin/users/?role=STUDENT&active=true")
        .then(setStudents)
        .catch(setError);
  }, [add]);
  if (group.loading) return <Loading />;
  if (!group.data) return <Alert error={group.error} />;
  const g = group.data;
  return (
    <>
      <div className="page-heading">
        <div>
          <p className="eyebrow">
            {g.code} · {g.level} · {g.academic_year}
          </p>
          <h1>{g.name}</h1>
          <p>{g.description}</p>
          <p>
            Enseignant : {g.teacher_name} ·{" "}
            {g.archived ? "Groupe archivé" : "Groupe actif"}
          </p>
        </div>
        {admin && (
          <div className="actions">
            <button className="btn_one" onClick={() => setEdit(true)}>
              Modifier le groupe
            </button>
            <button className="text-button" onClick={() => setDeleting(true)}>
              Supprimer le groupe vide
            </button>
          </div>
        )}
      </div>
      <section className="panel">
        <div className="panel-heading">
          <h2>
            {user!.role === "STUDENT"
              ? "Mon historique d’inscription"
              : "Étudiants et inscriptions"}
          </h2>
          {admin && !g.archived && (
            <button className="btn_one" onClick={() => setAdd(true)}>
              Inscrire un étudiant +
            </button>
          )}
        </div>
        <Alert error={enrollments.error} />
        {enrollments.loading ? (
          <Loading />
        ) : enrollments.data?.results.length ? (
          <>
            <div
              className="table-scroll"
              tabIndex={0}
              role="region"
              aria-label="Tableau à défilement horizontal"
            >
              <table>
                <thead>
                  <tr>
                    <th>Étudiant</th>
                    <th>Entrée</th>
                    <th>Sortie</th>
                    {admin && <th>Action</th>}
                  </tr>
                </thead>
                <tbody>
                  {enrollments.data.results.map((e) => (
                    <tr key={e.id}>
                      <td>{e.student_name}</td>
                      <td>{date(e.starts_at)}</td>
                      <td>{e.ends_at ? date(e.ends_at) : "En cours"}</td>
                      {admin && (
                        <td>
                          {!e.ends_at && (
                            <button
                              className="text-button"
                              onClick={() => setEnding(e)}
                            >
                              Terminer l’inscription
                              <span className="visually-hidden">
                                {" "}
                                de {e.student_name}
                              </span>
                            </button>
                          )}
                        </td>
                      )}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <Pagination
              page={page}
              count={enrollments.data.count}
              onChange={setPage}
            />
          </>
        ) : (
          <Empty>Aucune inscription pour ce groupe.</Empty>
        )}
      </section>
      {edit && (
        <Modal title="Modifier le groupe" onClose={() => setEdit(false)}>
          <GroupForm
            group={g}
            onDone={() => {
              setEdit(false);
              group.reload();
            }}
          />
        </Modal>
      )}
      {add && (
        <Modal title="Inscrire un étudiant" onClose={() => setAdd(false)}>
          <Alert error={error} />
          <Form
            onSuccess={() => {
              setAdd(false);
              enrollments.reload();
            }}
            onSubmit={(f) =>
              api("enrollments/", "POST", {
                group_id: id,
                student_id: val(f, "student_id"),
                starts_at: iso(val(f, "starts_at")),
                ends_at: val(f, "ends_at") ? iso(val(f, "ends_at")) : null,
              })
            }
          >
            <Select name="student_id" label="Étudiant actif" required>
              <option value="">Choisir un étudiant</option>
              {students.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.first_name} {s.last_name} · {s.email}
                </option>
              ))}
            </Select>
            <Field
              label="Entrée (heure de Tunis)"
              name="starts_at"
              type="datetime-local"
              defaultValue={localDateTime(new Date().toISOString())}
              required
            />
            <Field
              label="Sortie prévue (facultative)"
              name="ends_at"
              type="datetime-local"
            />
          </Form>
        </Modal>
      )}
      {ending && (
        <Modal title="Terminer une inscription" onClose={() => setEnding(null)}>
          <p className="intro">
            L’historique de {ending.student_name} sera conservé.
          </p>
          <Form
            onSuccess={() => {
              setEnding(null);
              enrollments.reload();
            }}
            onSubmit={(f) =>
              api("enrollments/" + ending.id + "/", "PATCH", {
                ends_at: iso(val(f, "ends_at")),
              })
            }
          >
            <Field
              label="Sortie (heure de Tunis)"
              name="ends_at"
              type="datetime-local"
              defaultValue={localDateTime(new Date().toISOString())}
              required
            />
          </Form>
        </Modal>
      )}
      {deleting && (
        <Modal title="Supprimer ce groupe ?" onClose={() => setDeleting(false)}>
          <p className="intro">
            Seul un groupe sans inscription ni séance peut être supprimé.
            Préférez l’archivage pour conserver un historique.
          </p>
          <Form
            label="Confirmer la suppression"
            onSubmit={() => api("groups/" + id + "/", "DELETE")}
            onSuccess={() => window.location.assign("/administration/groupes")}
          />
        </Modal>
      )}
    </>
  );
}
