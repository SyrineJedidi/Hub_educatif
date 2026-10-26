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
export default function GroupForm({
  group,
  onDone,
}: {
  group?: Group;
  onDone: () => void;
}) {
  const [teachers, setTeachers] = useState<User[]>([]),
    [error, setError] = useState<unknown>();
  useEffect(() => {
    allPages<User>("admin/users/?role=TEACHER&active=true")
      .then(setTeachers)
      .catch(setError);
  }, []);
  return (
    <>
      <Alert error={error} />
      <Form
        onSuccess={onDone}
        onSubmit={(f) =>
          api(
            "groups/" + (group ? group.id + "/" : ""),
            group ? "PATCH" : "POST",
            {
              name: val(f, "name"),
              code: val(f, "code"),
              description: val(f, "description"),
              level: val(f, "level"),
              academic_year: val(f, "academic_year"),
              teacher_id: val(f, "teacher_id"),
              archived: val(f, "archived") === "true",
            },
          )
        }
      >
        <div className="form-grid">
          <Field
            name="name"
            label="Nom du groupe"
            defaultValue={group?.name}
            required
            maxLength={120}
          />
          <Field
            name="code"
            label="Code unique"
            defaultValue={group?.code}
            pattern="[A-Za-z0-9_-]+"
            required
            maxLength={30}
          />
          <Field
            name="level"
            label="Niveau"
            defaultValue={group?.level}
            required
            maxLength={80}
          />
          <Field
            name="academic_year"
            label="Année universitaire"
            placeholder="2026–2027"
            defaultValue={group?.academic_year}
            required
            maxLength={30}
          />
        </div>
        <Field
          name="description"
          label="Description (facultative)"
          defaultValue={group?.description}
        />
        <Select
          name="teacher_id"
          label="Enseignant responsable"
          defaultValue={group?.teacher_id || ""}
          required
        >
          <option value="">Choisir un enseignant actif</option>
          {teachers.map((t) => (
            <option key={t.id} value={t.id}>
              {t.first_name} {t.last_name}
            </option>
          ))}
        </Select>
        {group && (
          <Select
            name="archived"
            label="Statut du groupe"
            defaultValue={String(group.archived)}
          >
            <option value="false">Actif</option>
            <option value="true">Archivé</option>
          </Select>
        )}
      </Form>
    </>
  );
}
