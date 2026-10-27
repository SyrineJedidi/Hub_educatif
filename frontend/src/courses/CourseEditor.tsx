import { useEffect, useId, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api, allPages } from "../api/client";
import { useResource } from "../hooks/useResource";
import type { Group, User } from "../api/types";
import {
  Alert,
  Field,
  Form,
  Loading,
  Select,
  Textarea,
} from "../components/UI";
import UnsavedChanges from "../quizzes/UnsavedChanges";
import { useFormValidation } from "../quizzes/useFormValidation";
import type { Course, Subject, SubjectSummary } from "./types";
import { useCourseContext } from "./useCourseContext";
import {
  COURSE_DESCRIPTION_MAX_LENGTH,
  MAX_GROUPS,
  TITLE_MAX_LENGTH,
  validateCourse,
} from "./validation";
import "./courses.css";
export default function CourseEditor() {
  const { id } = useParams();
  return (
    <div className="course-module">
      <div className="page-heading">
        <div>
          <p className="eyebrow">ATELIER DE COURS</p>
          <h1>{id ? "Modifier le cours" : "Créer un cours"}</h1>
          <p>
            {id
              ? "Mettez à jour la présentation, la matière et les groupes du cours."
              : "Présentez le cours et choisissez ses groupes. Vous ajouterez ensuite les chapitres et les ressources."}
          </p>
        </div>
      </div>
      {id ? <ExistingCourse id={id} /> : <CourseForm />}
    </div>
  );
}
function ExistingCourse({ id }: { id: string }) {
  const { base } = useCourseContext();
  const { data, error, loading, reload } = useResource<Course>(
    "courses/" + id + "/",
  );
  if (loading) return <Loading />;
  if (!data)
    return (
      <section className="panel">
        <Alert error={error} />
        <button className="text-button" onClick={reload}>
          Réessayer le chargement
        </button>
      </section>
    );
  if (data.status === "ARCHIVED")
    return (
      <section className="panel">
        <Alert error="Ce cours est archivé. Restaurez-le pour le modifier." />
        <Link className="text-button" to={base + "/" + data.id}>
          Revenir au cours ↗
        </Link>
      </section>
    );
  return <CourseForm key={data.id} course={data} />;
}
const sameSet = (a: string[], b: string[]) =>
  [...a].sort().join() === [...b].sort().join();
function CourseForm({ course }: { course?: Course }) {
  const { admin, base } = useCourseContext(),
    navigate = useNavigate();
  const saved = useRef(false),
    groupsHelp = useId(),
    groupsError = useId();
  const [title, setTitle] = useState(course?.title || ""),
    [description, setDescription] = useState(course?.description || ""),
    [subject, setSubject] = useState(course?.subject.id || ""),
    [teacher, setTeacher] = useState(course?.teacher.id || ""),
    [selected, setSelected] = useState<string[]>(
      (course?.groups || []).filter((g) => !g.archived).map((g) => g.id),
    );
  const [dirty, setDirty] = useState(false),
    [subjects, setSubjects] = useState<Subject[]>([]),
    [groups, setGroups] = useState<Group[]>([]),
    [teachers, setTeachers] = useState<User[]>([]),
    [error, setError] = useState<unknown>();
  useEffect(() => {
    let active = true;
    const fail = (e: unknown) => {
      if (active) setError(e);
    };
    allPages<Subject>("subjects/?archived=false")
      .then((items) => {
        if (active) setSubjects(items);
      })
      .catch(fail);
    allPages<Group>("groups/?archived=false")
      .then((items) => {
        if (active) setGroups(items);
      })
      .catch(fail);
    if (admin)
      allPages<User>("admin/users/?role=TEACHER&active=true")
        .then((items) => {
          if (active) setTeachers(items);
        })
        .catch(fail);
    return () => {
      active = false;
    };
  }, [admin]);
  // An archived subject stays selectable only for the course that already uses it.
  const subjectOptions: (SubjectSummary & { archived?: boolean })[] =
    course && !subjects.some((s) => s.id === course.subject.id)
      ? [...subjects, { ...course.subject, archived: true }]
      : subjects;
  const available = groups.filter(
    (g) => !g.archived && (!admin || g.teacher_id === teacher),
  );
  const archivedLinks = (course?.groups || []).filter((g) => g.archived);
  const validation = useFormValidation(
    () =>
      validateCourse(
        { title, description, subject, groups: selected, teacher },
        {
          subjects: subjectOptions.map((s) => s.id),
          groups: available.map((g) => g.id),
          teachers: admin
            ? teachers
                .filter((t) => t.is_active && t.role === "TEACHER")
                .map((t) => t.id)
            : undefined,
        },
      ),
    {
      title,
      description,
      subject_id: subject,
      group_ids: selected.join(","),
      teacher_id: teacher,
    },
  );
  const errorFor = (field: string) => validation.errors[field];
  async function submit() {
    validation.check();
    const body: Record<string, unknown> = {
      title: title.trim(),
      description: description.trim(),
    };
    // Unchanged links are not resent so an archived subject or group stays as it is.
    if (!course || subject !== course.subject.id) body.subject_id = subject;
    if (
      !course ||
      !sameSet(
        selected,
        (course.groups || []).filter((g) => !g.archived).map((g) => g.id),
      )
    )
      body.group_ids = selected;
    if (admin && (!course || teacher !== course.teacher.id))
      body.teacher_id = teacher;
    try {
      const result = await api<Course>(
        course ? "courses/" + course.id + "/" : "courses/",
        course ? "PATCH" : "POST",
        body,
      );
      saved.current = true;
      setDirty(false);
      navigate(base + "/" + result.id, { replace: true });
    } catch (e) {
      validation.serverErrors(e);
      throw e;
    }
  }
  return (
    <>
      <UnsavedChanges dirty={dirty} ignore={saved} />
      <Alert error={error} />
      <div className="course-form" onChange={() => setDirty(true)}>
        <Form
          {...validation.formProps}
          onSubmit={submit}
          label={course ? "Enregistrer les modifications" : "Créer le cours"}
        >
          <p className="field-help">
            Le titre, la description, la matière et au moins un groupe sont
            obligatoires.
          </p>
          <section className="panel">
            <h2>La présentation du cours</h2>
            <Field
              label="Titre du cours"
              name="title"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              required
              maxLength={TITLE_MAX_LENGTH}
              error={errorFor("title")}
            />
            <Textarea
              label="Description"
              name="description"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              maxLength={COURSE_DESCRIPTION_MAX_LENGTH}
              rows={5}
              required
              error={errorFor("description")}
            />
            <Select
              label="Matière"
              name="subject_id"
              value={subject}
              required
              onChange={(e) => setSubject(e.target.value)}
              error={errorFor("subject_id")}
            >
              <option value="">Choisir une matière active</option>
              {subjectOptions.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name} · {s.code}
                  {s.archived ? " (archivée)" : ""}
                </option>
              ))}
            </Select>
          </section>
          <section className="panel">
            <h2>L’enseignant et les groupes</h2>
            {admin && (
              <Select
                label="Enseignant propriétaire"
                name="teacher_id"
                value={teacher}
                required
                onChange={(e) => {
                  setTeacher(e.target.value);
                  setSelected([]);
                }}
                error={errorFor("teacher_id")}
              >
                <option value="">Choisir un enseignant actif</option>
                {teachers.map((t) => (
                  <option key={t.id} value={t.id}>
                    {t.first_name} {t.last_name}
                  </option>
                ))}
              </Select>
            )}
            <fieldset
              className="course-group-fieldset"
              aria-describedby={
                errorFor("group_ids") ? groupsError : groupsHelp
              }
            >
              <legend>Groupes pédagogiques</legend>
              <p id={groupsHelp} className="field-help">
                Cochez de 1 à {MAX_GROUPS} groupes actifs affectés à
                l’enseignant. Les étudiants actuellement inscrits dans ces
                groupes verront le cours une fois publié.
              </p>
              {available.length ? (
                <div className="course-checkbox-grid">
                  {available.map((g) => (
                    <label className="course-checkbox" key={g.id}>
                      <input
                        type="checkbox"
                        name="group_ids"
                        value={g.id}
                        checked={selected.includes(g.id)}
                        aria-invalid={errorFor("group_ids") ? true : undefined}
                        onChange={(e) => {
                          const checked = e.target.checked;
                          setSelected((current) =>
                            checked
                              ? [...current, g.id]
                              : current.filter((id) => id !== g.id),
                          );
                        }}
                      />
                      <span>
                        {g.name} · {g.code}
                      </span>
                    </label>
                  ))}
                </div>
              ) : (
                <p className="notice">
                  {admin && !teacher
                    ? "Choisissez d’abord l’enseignant propriétaire pour afficher ses groupes."
                    : "Aucun groupe actif n’est affecté à cet enseignant pour le moment."}
                </p>
              )}
              {archivedLinks.length > 0 && (
                <p className="field-help">
                  Groupe(s) archivé(s) encore associé(s) :{" "}
                  {archivedLinks.map((g) => g.name).join(", ")}. Ils seront
                  retirés si vous modifiez la sélection.
                </p>
              )}
              {errorFor("group_ids") && (
                <p id={groupsError} className="field-help notice-error">
                  {errorFor("group_ids")}
                </p>
              )}
            </fieldset>
          </section>
          <div className="course-form-cancel">
            <section className="panel">
              <h2>Visibilité et diffusion</h2>
              <p>
                {course
                  ? "Les modifications s’appliquent immédiatement, y compris pour un cours déjà publié."
                  : "Le cours est créé en brouillon : il reste visible pour vous et l’administrateur uniquement."}
              </p>
              <p>
                Ajoutez ensuite au moins un chapitre et une ressource, puis
                choisissez « Publier le cours » depuis sa page pour le rendre
                visible aux étudiants des groupes sélectionnés.
              </p>
            </section>
            <Link to={course ? base + "/" + course.id : base}>Annuler</Link>
          </div>
        </Form>
      </div>
    </>
  );
}
