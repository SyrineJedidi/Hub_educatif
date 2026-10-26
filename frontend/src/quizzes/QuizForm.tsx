import { t } from "./i18n";
import { useEffect, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api, allPages, iso } from "../api/client";
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
    [attempts, setAttempts] = useState(String(quiz?.max_attempts || 1)),
    [opens, setOpens] = useState(localDate(quiz?.opens_at)),
    [closes, setCloses] = useState(localDate(quiz?.closes_at));
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
          opens_at: opens,
          closes_at: closes,
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
      opens_at: opens,
      closes_at: closes,
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
      opens_at: opens ? iso(opens) : null,
      closes_at: closes ? iso(closes) : null,
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
              ? t("Dupliquer en nouveau brouillon")
              : t("Enregistrer le brouillon")
          }
        >
          <p className="field-help">
            {t(
              "Les dates sont facultatives. Les autres champs sont obligatoires. Choisissez explicitement une durée limitée ou sans limite de temps. ",
            )}
          </p>
          <section className="panel">
            <h2>{t("Le contenu du quiz")}</h2>
            <p className="field-help">
              {t(
                "Un titre clair et une courte présentation pour situer les apprentissages. ",
              )}
            </p>
            <Field
              label={t("Titre du quiz")}
              name="title"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              required
              maxLength={QUIZ_TITLE_MAX_LENGTH}
              error={errorFor("title")}
            />
            <Textarea
              label={t("Description")}
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
            <h2>{t("Le groupe et l’enseignant")}</h2>
            {admin && (
              <Select
                label={t("Enseignant propriétaire")}
                name="teacher_id"
                value={teacher}
                required
                onChange={(e) => {
                  setTeacher(e.target.value);
                  setGroup("");
                }}
                error={errorFor("teacher_id")}
              >
                <option value="">{t("Choisir un enseignant actif")}</option>
                {teachers.map((t) => (
                  <option key={t.id} value={t.id}>
                    {t.first_name} {t.last_name}
                  </option>
                ))}
              </Select>
            )}
            <Select
              label={t("Groupe pédagogique")}
              name="learning_group_id"
              value={group}
              required
              onChange={(e) => setGroup(e.target.value)}
              error={errorFor("learning_group_id")}
            >
              <option value="">{t("Choisir un groupe actif")}</option>
              {groups
                .filter((g) => !admin || g.teacher_id === teacher)
                .map((g) => (
                  <option key={g.id} value={g.id}>
                    {g.name} · {g.code}
                  </option>
                ))}
            </Select>
            <p className="field-help">
              {t(
                "Seuls les groupes actifs affectés à l’enseignant peuvent recevoir ce quiz. ",
              )}
            </p>
          </section>
          <section className="panel">
            <h2>{t("Les paramètres pédagogiques")}</h2>
            <div className="form-grid">
              <Select
                label={t("Niveau du quiz")}
                name="level"
                value={level}
                onChange={(e) => setLevel(e.target.value as Quiz["level"])}
                required
                error={errorFor("level")}
              >
                <option value="">{t("Choisir un niveau")}</option>
                {Object.entries(levels).map(([key, label]) => (
                  <option key={key} value={key}>
                    {t(label)}
                  </option>
                ))}
              </Select>
              <Field
                label={t("Tentatives autorisées")}
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
                label={t("Durée du quiz")}
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
                <option value="">{t("Choisir la durée")}</option>
                <option value="unlimited">{t("Sans limite de temps")}</option>
                <option value="limited">{t("Durée limitée")}</option>
              </Select>
              {durationMode === "limited" && (
                <Field
                  label={t("Durée en minutes")}
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
              {t(
                "La durée et le nombre de tentatives autorisées s’appliquent aux passages des étudiants. ",
              )}
            </p>
          </section>
          <section className="panel">
            <h2>{t("Disponibilité du quiz")}</h2>
            <p>
              {t(
                "Dates facultatives, fuseau Africa/Tunis (UTC+01:00). Sans dates, le fonctionnement actuel est conservé.",
              )}
            </p>
            <div className="form-grid">
              <Field
                label={t("Ouverture (facultatif)")}
                name="opens_at"
                type="datetime-local"
                value={opens}
                onChange={(e) => setOpens(e.target.value)}
                error={errorFor("opens_at")}
              />
              <Field
                label={t("Fermeture (facultatif)")}
                name="closes_at"
                type="datetime-local"
                value={closes}
                onChange={(e) => setCloses(e.target.value)}
                error={errorFor("closes_at")}
              />
            </div>
            <p className="field-help">
              {t(
                "Au départ, l’échéance est la plus proche entre la durée autorisée et la fermeture. Les dates sont verrouillées après publication.",
              )}
            </p>
          </section>
          <div className="quiz-form-cancel">
            <section className="panel">
              <h2>{t("Visibilité et diffusion")}</h2>
              <p>
                {t(
                  "Enregistrez ce quiz en brouillon pour le garder dans votre espace et celui de l’administrateur, sans l’afficher aux étudiants. ",
                )}
              </p>
              <p>
                {t(
                  "Quand les questions sont prêtes, choisissez « Publier le quiz » depuis la prévisualisation pour le rendre visible aux étudiants actuellement inscrits dans le groupe sélectionné. ",
                )}
              </p>
              <p>
                {t(
                  "Après publication, l’action « Archiver » le masque aux étudiants tout en le conservant pour vous et l’administrateur. ",
                )}
              </p>
            </section>
            <Link to={quiz ? base + "/" + quiz.id : base}>{t("Annuler")}</Link>
          </div>
        </Form>
      </div>
    </>
  );
}
function localDate(value?: string | null) {
  return value
    ? new Intl.DateTimeFormat("sv-SE", {
        timeZone: "Africa/Tunis",
        year: "numeric",
        month: "2-digit",
        day: "2-digit",
        hour: "2-digit",
        minute: "2-digit",
      })
        .format(new Date(value))
        .replace(" ", "T")
    : "";
}
