import { useEffect, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api, allPages } from "../api/client";
import type { Group, User } from "../api/types";
import { Field, Select, Textarea, Form, Alert } from "../components/UI";
import { levels } from "./types";
import type { Quiz } from "./types";
import { useQuizContext } from "./useQuizContext";
import UnsavedChanges from "./UnsavedChanges";
import {
  validateQuiz,
  QUIZ_TITLE_MAX_LENGTH,
  duplicateTitle,
} from "./validation";
import { useFormValidation } from "./useFormValidation";
export default function QuizForm({
  quiz,
  duplicate = false,
}: {
  quiz?: Quiz;
  duplicate?: boolean;
}) {
  const { admin, base } = useQuizContext(),
    navigate = useNavigate();
  const saved = useRef(false);
  const [title, setTitle] = useState(
      duplicate ? duplicateTitle(quiz!.title) : quiz?.title || "",
    ),
    [description, setDescription] = useState(quiz?.description || ""),
    [teacher, setTeacher] = useState(quiz?.teacher_id || ""),
    [group, setGroup] = useState(quiz?.learning_group_id || ""),
    [level, setLevel] = useState(quiz?.level || ""),
    [durationMode, setDurationMode] = useState(
      quiz ? (quiz.duration_minutes === null ? "unlimited" : "limited") : "",
    ),
    [duration, setDuration] = useState(
      quiz?.duration_minutes == null ? "" : String(quiz.duration_minutes),
    ),
    [attempts, setAttempts] = useState(String(quiz?.max_attempts || 1));
  const [dirty, setDirty] = useState(false),
    [groups, setGroups] = useState<Group[]>([]),
    [teachers, setTeachers] = useState<User[]>([]),
    [error, setError] = useState<unknown>();
  const validation = useFormValidation(
    () =>
      validateQuiz(
        {
          title,
          description,
          teacher,
          group,
          level,
          durationMode,
          duration,
          attempts,
        },
        groups,
        teachers,
        admin,
      ),
    {
      title,
      description,
      teacher_id: teacher,
      learning_group_id: group,
      level,
      duration_mode: durationMode,
      duration_minutes: durationMode === "limited" ? duration : null,
      max_attempts: attempts,
    },
  );
  useEffect(() => {
    allPages<Group>("groups/?archived=false").then(setGroups).catch(setError);
    if (admin)
      allPages<User>("admin/users/?role=TEACHER&active=true")
        .then(setTeachers)
        .catch(setError);
  }, [admin]);
  const errorFor = (field: string) => validation.errors[field];
  async function submit() {
    validation.check();
    const body = {
      title: title.trim(),
      description: description.trim(),
      learning_group_id: group,
      level,
      duration_minutes: durationMode === "unlimited" ? null : Number(duration),
      max_attempts: Number(attempts),
      ...(admin ? { teacher_id: teacher } : {}),
    };
    try {
      const result = await api<Quiz>(
        "quizzes/" +
          (quiz ? quiz.id + "/" + (duplicate ? "duplicate/" : "") : ""),
        quiz && !duplicate ? "PATCH" : "POST",
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
      <div onChange={() => setDirty(true)}>
        <Form
          {...validation.formProps}
          onSubmit={submit}
          label={
            duplicate
              ? "Dupliquer en nouveau brouillon"
              : "Enregistrer le brouillon"
          }
        >
          <p className="field-help">
            Tous les champs affichés sont obligatoires. Choisissez explicitement
            une durée limitée ou sans limite de temps.
          </p>
          <section className="panel">
            <h2>Le contenu du quiz</h2>
            <p className="field-help">
              Un titre clair et une courte présentation pour situer les
              apprentissages.
            </p>
            <Field
              label="Titre du quiz"
              name="title"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              required
              maxLength={QUIZ_TITLE_MAX_LENGTH}
              error={errorFor("title")}
            />
            <Textarea
              label="Description"
              name="description"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              maxLength={2000}
              rows={4}
              required
              error={errorFor("description")}
            />
          </section>
          <section className="panel">
            <h2>Le groupe et l’enseignant</h2>
            {admin && (
              <Select
                label="Enseignant propriétaire"
                name="teacher_id"
                value={teacher}
                required
                onChange={(e) => {
                  setTeacher(e.target.value);
                  setGroup("");
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
            <Select
              label="Groupe pédagogique"
              name="learning_group_id"
              value={group}
              required
              onChange={(e) => setGroup(e.target.value)}
              error={errorFor("learning_group_id")}
            >
              <option value="">Choisir un groupe actif</option>
              {groups
                .filter((g) => !admin || g.teacher_id === teacher)
                .map((g) => (
                  <option key={g.id} value={g.id}>
                    {g.name} · {g.code}
                  </option>
                ))}
            </Select>
            <p className="field-help">
              Seuls les groupes actifs affectés à l’enseignant peuvent recevoir
              ce quiz.
            </p>
          </section>
          <section className="panel">
            <h2>Les paramètres pédagogiques</h2>
            <div className="form-grid">
              <Select
                label="Niveau du quiz"
                name="level"
                value={level}
                onChange={(e) => setLevel(e.target.value as Quiz["level"])}
                required
                error={errorFor("level")}
              >
                <option value="">Choisir un niveau</option>
                {Object.entries(levels).map(([key, label]) => (
                  <option key={key} value={key}>
                    {label}
                  </option>
                ))}
              </Select>
              <Field
                label="Tentatives autorisées"
                name="max_attempts"
                type="number"
                min={1}
                max={10}
                step={1}
                required
                value={attempts}
                onChange={(e) => setAttempts(e.target.value)}
                error={errorFor("max_attempts")}
              />
              <Select
                label="Durée du quiz"
                name="duration_mode"
                value={durationMode}
                onChange={(e) => setDurationMode(e.target.value)}
                required
                error={
                  errorFor("duration_mode") ||
                  (durationMode === "unlimited"
                    ? errorFor("duration_minutes")
                    : undefined)
                }
              >
                <option value="">Choisir la durée</option>
                <option value="unlimited">Sans limite de temps</option>
                <option value="limited">Durée limitée</option>
              </Select>
              {durationMode === "limited" && (
                <Field
                  label="Durée en minutes"
                  name="duration_minutes"
                  type="number"
                  min={1}
                  max={2147483647}
                  step={1}
                  required
                  value={duration}
                  onChange={(e) => setDuration(e.target.value)}
                  error={errorFor("duration_minutes")}
                />
              )}
            </div>
            <p className="field-help">
              La durée et le nombre de tentatives autorisées s’appliquent aux
              passages des étudiants.
            </p>
          </section>
          <div className="quiz-form-cancel">
            <section className="panel">
              <h2>Visibilité et diffusion</h2>
              <p>
                Enregistrez ce quiz en brouillon pour le garder dans votre
                espace et celui de l’administrateur, sans l’afficher aux
                étudiants.
              </p>
              <p>
                Quand les questions sont prêtes, choisissez « Publier le quiz »
                depuis la prévisualisation pour le rendre visible aux étudiants
                actuellement inscrits dans le groupe sélectionné.
              </p>
              <p>
                Après publication, l’action « Archiver » le masque aux étudiants
                tout en le conservant pour vous et l’administrateur.
              </p>
            </section>
            <Link to={quiz ? base + "/" + quiz.id : base}>Annuler</Link>
          </div>
        </Form>
      </div>
    </>
  );
}
