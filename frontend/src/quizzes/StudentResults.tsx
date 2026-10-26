import { t, n, LanguageNotice } from "./i18n";
import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { allPages, date, query, ApiError } from "../api/client";
import { useResource } from "../hooks/useResource";
import type { Group, Page, User } from "../api/types";
import {
  Alert,
  Badge,
  Empty,
  Field,
  Loading,
  Pagination,
  Select,
} from "../components/UI";
import { useQuizContext } from "./useQuizContext";
import { attemptLabels } from "./attemptTypes";
import type { ManagedResult } from "./resultTypes";
import { personName, percentageLabel } from "./resultTypes";
import type { Quiz } from "./types";
import "./quiz.css";
import { ManagerFeedback } from "./Feedback";
import { quizLanguage } from "./i18n";

export default function StudentResults() {
  const { id } = useParams();
  const { admin } = useQuizContext();
  const base = admin ? "/administration" : "/espace";
  const [search, setSearch] = useState(""),
    [status, setStatus] = useState(""),
    [quiz, setQuiz] = useState(""),
    [group, setGroup] = useState(""),
    [teacher, setTeacher] = useState(""),
    [page, setPage] = useState(1);
  const [quizzes, setQuizzes] = useState<Quiz[]>([]),
    [groups, setGroups] = useState<Group[]>([]),
    [teachers, setTeachers] = useState<User[]>([]),
    [filterError, setFilterError] = useState<unknown>();
  const [exporting, setExporting] = useState(false);
  useEffect(() => {
    let active = true;
    allPages<Quiz>("quizzes/")
      .then((items) => {
        if (active) setQuizzes(items);
      })
      .catch(setFilterError);
    if (admin)
      Promise.all([
        allPages<Quiz>("quizzes/"),
        allPages<Group>("groups/"),
        allPages<User>("admin/users/?role=TEACHER"),
      ])
        .then(([quizzes, groups, teachers]) => {
          if (active) {
            setQuizzes(quizzes);
            setGroups(groups);
            setTeachers(teachers);
          }
        })
        .catch((error) => {
          if (active) setFilterError(error);
        });
    return () => {
      active = false;
    };
  }, [admin]);
  useEffect(() => {
    setPage(1);
  }, [id]);
  const endpoint = id ? `quizzes/${id}/results/` : "quizzes/results/";
  const { data, loading, error, reload } = useResource<
    Page<ManagedResult> & { quiz?: { id: string; title: string } }
  >(endpoint + "?" + query({ q: search, status, quiz, group, teacher, page }));
  const filtered = !!(search || status || quiz || group || teacher);
  function filter(setter: (value: string) => void, value: string) {
    setter(value);
    setPage(1);
  }
  async function exportPDF() {
    if (exporting || !(id || quiz)) return;
    setExporting(true);
    setFilterError(undefined);
    try {
      const response = await fetch(
        `/api/quizzes/${id || quiz}/grades.pdf?lang=${quizLanguage()}`,
        { credentials: "same-origin" },
      );
      if (!response.ok) {
        const body = await response.json();
        throw new ApiError(
          response.status,
          body.error?.message || t("Export impossible."),
        );
      }
      const url = URL.createObjectURL(await response.blob());
      const link = document.createElement("a");
      link.href = url;
      link.download = "notes-quiz.pdf";
      link.click();
      setTimeout(() => URL.revokeObjectURL(url), 10000);
    } catch (error) {
      setFilterError(error);
    } finally {
      setExporting(false);
    }
  }
  return (
    <div className="quiz-module">
      <LanguageNotice />
      <div className="page-heading">
        <div>
          <p className="eyebrow">{t("SUIVRE LES APPRENTISSAGES")}</p>
          <h1>{t("Résultats des étudiants")}</h1>
          <p>
            {data?.quiz && !error
              ? data.quiz.title
              : admin
                ? t("Consultez les tentatives de tous les quiz.")
                : t("Consultez les tentatives des étudiants de vos quiz.")}
          </p>
        </div>
        <Link
          className="text-button"
          to={id ? `${base}/quiz/${id}` : `${base}/quiz`}
        >
          {id ? t("Revenir au quiz") : t("Revenir aux quiz")} ↗
        </Link>
      </div>
      <div className="actions">
        <button
          className="btn_one"
          disabled={exporting || !(id || quiz)}
          onClick={() => void exportPDF()}
        >
          {exporting ? t("Export en cours…") : t("Exporter les notes en PDF")}
        </button>
        {!id && !quiz && (
          <p>{t("Choisissez un quiz pour exporter les notes.")}</p>
        )}
      </div>
      {!id && !admin && (
        <Select
          label={t("Quiz")}
          value={quiz}
          onChange={(e) => filter(setQuiz, e.target.value)}
        >
          <option value="">{t("Tous les quiz")}</option>
          {quizzes.map((item) => (
            <option key={item.id} value={item.id}>
              {item.title}
            </option>
          ))}
        </Select>
      )}
      {id && (
        <p>
          <Link className="text-button" to={`${base}/resultats-quiz`}>
            {admin
              ? t("Tous les résultats des quiz")
              : t("Résultats de tous mes quiz")}{" "}
            ↗
          </Link>
        </p>
      )}
      <section
        className="panel quiz-filters"
        aria-label={t("Rechercher et filtrer les résultats")}
      >
        <div className="filters">
          <Field
            label={t("Rechercher un étudiant")}
            type="search"
            placeholder={t("Nom ou prénom")}
            maxLength={200}
            value={search}
            onChange={(event) => filter(setSearch, event.target.value)}
          />
          <Select
            label={t("Statut de la tentative")}
            value={status}
            onChange={(event) => filter(setStatus, event.target.value)}
          >
            <option value="">{t("Tous les statuts")}</option>
            {Object.entries(attemptLabels).map(([key, label]) => (
              <option key={key} value={key}>
                {t(label)}
              </option>
            ))}
          </Select>
          {admin && (
            <>
              {!id && (
                <Select
                  label={t("Quiz")}
                  value={quiz}
                  onChange={(event) => filter(setQuiz, event.target.value)}
                >
                  <option value="">{t("Tous les quiz")}</option>
                  {quizzes.map((quiz) => (
                    <option key={quiz.id} value={quiz.id}>
                      {quiz.title}
                    </option>
                  ))}
                </Select>
              )}
              <Select
                label={t("Groupe")}
                value={group}
                onChange={(event) => filter(setGroup, event.target.value)}
              >
                <option value="">{t("Tous les groupes")}</option>
                {groups.map((group) => (
                  <option key={group.id} value={group.id}>
                    {group.name}
                  </option>
                ))}
              </Select>
              <Select
                label={t("Enseignant")}
                value={teacher}
                onChange={(event) => filter(setTeacher, event.target.value)}
              >
                <option value="">{t("Tous les enseignants")}</option>
                {teachers.map((teacher) => (
                  <option key={teacher.id} value={teacher.id}>
                    {personName(teacher)}
                  </option>
                ))}
              </Select>
            </>
          )}
        </div>
        {filtered && (
          <button
            className="text-button"
            onClick={() => {
              setSearch("");
              setStatus("");
              setQuiz("");
              setGroup("");
              setTeacher("");
              setPage(1);
            }}
          >
            {t("Réinitialiser les filtres ")}
          </button>
        )}
        <Alert error={filterError} />
      </section>
      {loading ? (
        <Loading />
      ) : error || !data ? (
        <section className="panel">
          <Alert error={error} />
          <button className="text-button" onClick={reload}>
            {t("Réessayer le chargement ")}
          </button>
        </section>
      ) : (
        <section className="panel">
          <div className="panel-heading">
            <h2>
              {n(data.count)}
              {t(" tentative(s)")}
            </h2>
            <button className="text-button" onClick={reload}>
              {t("Actualiser les résultats ")}
            </button>
          </div>
          {data.results.length ? (
            <div
              className="table-scroll quiz-results-scroll"
              role="region"
              aria-label={t("Tentatives des étudiants")}
              tabIndex={0}
            >
              <table className="quiz-results-table">
                <caption>
                  {t("Tentatives commencées et résultats des étudiants ")}
                </caption>
                <thead>
                  <tr>
                    <th scope="col">{t("Étudiant")}</th>
                    {!id && <th scope="col">{t("Quiz")}</th>}
                    <th scope="col">{t("Groupe")}</th>
                    <th scope="col" className="quiz-number-cell">
                      {t("Tentative")}
                    </th>
                    <th scope="col">{t("Statut")}</th>
                    <th scope="col">{t("Début")}</th>
                    <th scope="col" className="quiz-score-cell">
                      {t("Score")}
                    </th>
                    <th scope="col">{t("Consultation")}</th>
                  </tr>
                </thead>
                <tbody>
                  {data.results.map((attempt) => (
                    <tr key={attempt.id}>
                      <th scope="row">
                        {personName(attempt.student) || t("Étudiant")}
                      </th>
                      {!id && (
                        <td>
                          {attempt.quiz_title}
                          {admin && (
                            <small className="quiz-result-owner">
                              {personName(attempt.teacher)}
                            </small>
                          )}
                        </td>
                      )}
                      <td>{attempt.learning_group.name}</td>
                      <td className="quiz-number-cell">
                        {t("N° ")}
                        {n(attempt.number)}
                      </td>
                      <td>
                        <Badge>{t(attemptLabels[attempt.status])}</Badge>
                      </td>
                      <td>{date(attempt.started_at)}</td>
                      <td className="quiz-score-cell">
                        {attempt.status === "IN_PROGRESS" ? (
                          <span>{t("En cours")}</span>
                        ) : (
                          <>
                            <strong>
                              {n(attempt.points_earned)} /{" "}
                              {n(attempt.total_points)}
                            </strong>
                            <small className="quiz-result-owner">
                              {attempt.percentage === null
                                ? t("Résultat indisponible")
                                : percentageLabel(attempt.percentage)}
                            </small>
                          </>
                        )}
                      </td>
                      <td>
                        <Link
                          className="text-button"
                          to={`${base}/resultats-quiz/${attempt.id}`}
                        >
                          {t("Voir les réponses ")}
                        </Link>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <Empty
              title={
                filtered
                  ? t("Aucun résultat")
                  : t("Aucune tentative pour le moment")
              }
            >
              {filtered
                ? t(
                    "Aucune tentative ne correspond à vos filtres. Modifiez la recherche ou réinitialisez les filtres.",
                  )
                : t(
                    "Les étudiants apparaîtront ici dès qu’ils commenceront une tentative.",
                  )}
            </Empty>
          )}
          <Pagination page={page} count={data.count} onChange={setPage} />
        </section>
      )}
      {(id || quiz) && <ManagerFeedback quizId={(id || quiz)!} />}
    </div>
  );
}
