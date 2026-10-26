import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { api, allPages, date, iso, localDateTime, query } from "../api/client";
import type { Group, Page, Session } from "../api/types";
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
  statuses,
} from "../components/UI";
export default function SessionForm({
  session,
  onDone,
}: {
  session?: Session;
  onDone: () => void;
}) {
  const [groups, setGroups] = useState<Group[]>([]),
    [error, setError] = useState<unknown>();
  useEffect(() => {
    allPages<Group>("groups/").then(setGroups).catch(setError);
  }, []);
  return (
    <>
      <Alert error={error} />
      <Form
        onSuccess={onDone}
        onSubmit={(f) =>
          api(
            "sessions/" + (session ? session.id + "/" : ""),
            session ? "PATCH" : "POST",
            {
              group_id: val(f, "group_id"),
              title: val(f, "title"),
              description: val(f, "description"),
              starts_at: iso(val(f, "starts_at")),
              ends_at: iso(val(f, "ends_at")),
              location: val(f, "location"),
              status: val(f, "status") || "PLANNED",
            },
          )
        }
      >
        <Select
          name="group_id"
          label="Groupe"
          defaultValue={session?.group_id || ""}
          required
        >
          <option value="">Choisir un groupe</option>
          {groups
            .filter((g) => !g.archived || g.id === session?.group_id)
            .map((g) => (
              <option key={g.id} value={g.id}>
                {g.name} · {g.code}
              </option>
            ))}
        </Select>
        <Field
          label="Titre"
          name="title"
          defaultValue={session?.title}
          required
          maxLength={180}
        />
        <Field
          label="Description (facultative)"
          name="description"
          defaultValue={session?.description}
        />
        <div className="form-grid">
          <Field
            label="Début (heure de Tunis)"
            name="starts_at"
            type="datetime-local"
            defaultValue={
              session ? localDateTime(session.starts_at) : undefined
            }
            required
          />
          <Field
            label="Fin (heure de Tunis)"
            name="ends_at"
            type="datetime-local"
            defaultValue={session ? localDateTime(session.ends_at) : undefined}
            required
          />
        </div>
        <Field
          label="Salle ou lien de visioconférence"
          name="location"
          defaultValue={session?.location}
          maxLength={300}
        />
        {session && (
          <Select label="Statut" name="status" defaultValue={session.status}>
            {["PLANNED", "COMPLETED"].map((s) => (
              <option key={s} value={s}>
                {statuses[s]}
              </option>
            ))}
            {session.status === "CANCELLED" && (
              <option value="CANCELLED">Annulée</option>
            )}
          </Select>
        )}
      </Form>
    </>
  );
}
