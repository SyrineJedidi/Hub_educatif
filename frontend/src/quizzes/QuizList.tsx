import { t, n, LanguageNotice } from "./i18n";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { allPages, query } from "../api/client";
import { useResource } from "../hooks/useResource";
import type { Page, Group, User } from "../api/types";
import {
  Alert,
  Field,
  Select,
  Empty,
  Loading,
  Pagination,
} from "../components/UI";
import { useQuizContext } from "./useQuizContext";
import { levels, quizStatuses } from "./types";
import type { Quiz } from "./types";
import QuizSummary from "./QuizSummary";
import QuizActions from "./QuizActions";
import "./quiz.css";
export default function QuizList() {
  const { base, apiBase, student, admin } = useQuizContext();
  const [q, setQ] = useState(""),
    [level, setLevel] = useState(""),
    [status, setStatus] = useState(""),
    [group, setGroup] = useState(""),
    [teacher, setTeacher] = useState(""),
    [page, setPage] = useState(1);
  const [groups, setGroups] = useState<Group[]>([]),
    [teachers, setTeachers] = useState<User[]>([]),
    [filterError, setFilterError] = useState<unknown>();
  useEffect(() => {
    allPages<Group>("groups/").then(setGroups).catch(setFilterError);
    if (admin)
      allPages<User>("admin/users/?role=TEACHER")
        .then(setTeachers)
        .catch(setFilterError);
  }, [admin]);
  const { data, error, loading, reload } = useResource<Page<Quiz>>(
    apiBase + "?" + query({ q, level, status, group, teacher, page }),
  );
  const filtered = !!(q || level || status || group || teacher);
  function reset() {
    setQ("");
    setLevel("");
    setStatus("");
    setGroup("");
    setTeacher("");
    setPage(1);
  }
  return (
    <div className="quiz-module">
      <LanguageNotice />
      <div className="page-heading">
        <div>
          <p className="eyebrow">{t("QUIZ ET PROGRESSION · PREMIÈRE ÉTAPE")}</p>
          <h1>
            {admin
              ? t("Gestion des quiz")
              : student
                ? t("Quiz de mes groupes")
                : t("Mes quiz")}
          </h1>
          <p>
            {student
              ? t(
                  "Choisissez un quiz de vos groupes, répondez à votre rythme et consultez votre correction après soumission.",
                )
              : t(
                  "Concevez des QCM, organisez vos questions et publiez des contenus prêts à partager.",
                )}
          </p>
        </div>
        {!student && (
          <Link className="btn_one" to={base + "/nouveau"}>
            {t("Créer un quiz + ")}
          </Link>
        )}
        {student && (
          <Link className="text-button" to="/espace/tentatives">
            {t("Mes tentatives et corrections ↗ ")}
          </Link>
        )}
      </div>
      <section
        className="panel quiz-filters"
        aria-label={t("Rechercher et filtrer les quiz")}
      >
        <div className="filters">
          <Field
            label={t("Rechercher par titre")}
            type="search"
            value={q}
            maxLength={150}
            onChange={(e) => {
              setQ(e.target.value);
              setPage(1);
            }}
          />
          {!student && (
            <Select
              label={t("Statut")}
              value={status}
              onChange={(e) => {
                setStatus(e.target.value);
                setPage(1);
              }}
            >
              <option value="">{t("Tous les statuts")}</option>
              {Object.entries(quizStatuses).map(([key, label]) => (
                <option key={key} value={key}>
                  {t(label)}
                </option>
              ))}
            </Select>
          )}
          <Select
            label={t("Niveau")}
            value={level}
            onChange={(e) => {
              setLevel(e.target.value);
              setPage(1);
            }}
          >
            <option value="">{t("Tous les niveaux")}</option>
            {Object.entries(levels).map(([key, label]) => (
              <option key={key} value={key}>
                {t(label)}
              </option>
            ))}
          </Select>
          <Select
            label={t("Groupe")}
            value={group}
            onChange={(e) => {
              setGroup(e.target.value);
              setPage(1);
            }}
          >
            <option value="">{t("Tous mes groupes")}</option>
            {groups
              .filter((g) => !student || !g.archived)
              .map((g) => (
                <option key={g.id} value={g.id}>
                  {g.name}
                </option>
              ))}
          </Select>
          {admin && (
            <Select
              label={t("Enseignant")}
              value={teacher}
              onChange={(e) => {
                setTeacher(e.target.value);
                setPage(1);
              }}
            >
              <option value="">{t("Tous les enseignants")}</option>
              {teachers.map((t) => (
                <option value={t.id} key={t.id}>
                  {t.first_name} {t.last_name}
                </option>
              ))}
            </Select>
          )}
        </div>
        {filtered && (
          <button className="text-button" onClick={reset}>
            {t("Réinitialiser les filtres ")}
          </button>
        )}
      </section>
      <Alert error={error || filterError} />
      {loading ? (
        <Loading />
      ) : data?.results.length ? (
        <>
          <p className="field-help" role="status">
            {n(data.count)}
            {t(" quiz")}{" "}
            {filtered
              ? t("correspondent à vos filtres")
              : t("disponibles dans votre espace")}
            .
          </p>
          <div className="quiz-card-grid">
            {data.results.map((quiz) => (
              <article className="panel quiz-card" key={quiz.id}>
                <span
                  className="ti-help-alt quiz-card-icon"
                  aria-hidden="true"
                />
                <h2>
                  <Link to={base + "/" + quiz.id}>{quiz.title}</Link>
                </h2>
                <p className="quiz-description">
                  {quiz.description ||
                    t(
                      "Un quiz pour consolider les apprentissages de votre groupe.",
                    )}
                </p>
                <QuizSummary quiz={quiz} />
                <Link className="btn_one" to={base + "/" + quiz.id}>
                  {student
                    ? t("Voir la présentation")
                    : quiz.status === "DRAFT"
                      ? t("Gérer les questions")
                      : t("Consulter le quiz")}{" "}
                  ↗
                </Link>
                <QuizActions quiz={quiz} onDone={reload} />
              </article>
            ))}
          </div>
          <Pagination page={page} count={data.count} onChange={setPage} />
        </>
      ) : (
        <section className="panel">
          <Empty
            headingLevel={2}
            title={
              filtered
                ? t("Aucun résultat")
                : student
                  ? t("Aucun quiz pour le moment")
                  : t("Votre premier quiz vous attend")
            }
          >
            {filtered
              ? t(
                  "Aucun résultat pour ces critères. Essayez une autre recherche ou réinitialisez les filtres.",
                )
              : student
                ? t("Aucun quiz publié pour vos groupes actifs pour le moment.")
                : t(
                    "Votre premier quiz commence ici. Préparez un brouillon et ajoutez vos questions, à votre rythme.",
                  )}
          </Empty>
          <div className="quiz-empty-action">
            {filtered ? (
              <button className="btn_one" onClick={reset}>
                {t("Afficher tous les quiz ")}
              </button>
            ) : !student ? (
              <Link className="btn_one" to={base + "/nouveau"}>
                {t("Créer mon premier quiz + ")}
              </Link>
            ) : (
              <Link className="text-button" to="/espace/groupes">
                {t("Voir mes groupes ↗ ")}
              </Link>
            )}
          </div>
        </section>
      )}
    </div>
  );
}
