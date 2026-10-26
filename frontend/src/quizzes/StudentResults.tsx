import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { allPages, date, query } from "../api/client";
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
  useEffect(() => {
    let active = true;
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
  return (
    <div className="quiz-module">
      <div className="page-heading">
        <div>
          <p className="eyebrow">SUIVRE LES APPRENTISSAGES</p>
          <h1>Résultats des étudiants</h1>
          <p>
            {data?.quiz && !error
              ? data.quiz.title
              : admin
                ? "Consultez les tentatives de tous les quiz."
                : "Consultez les tentatives des étudiants de vos quiz."}
          </p>
        </div>
        <Link
          className="text-button"
          to={id ? `${base}/quiz/${id}` : `${base}/quiz`}
        >
          {id ? "Revenir au quiz" : "Revenir aux quiz"} ↗
        </Link>
      </div>
      {id && (
        <p>
          <Link className="text-button" to={`${base}/resultats-quiz`}>
            {admin
              ? "Tous les résultats des quiz"
              : "Résultats de tous mes quiz"}{" "}
            ↗
          </Link>
        </p>
      )}
      <section
        className="panel quiz-filters"
        aria-label="Rechercher et filtrer les résultats"
      >
        <div className="filters">
          <Field
            label="Rechercher un étudiant"
            type="search"
            placeholder="Nom ou prénom"
            maxLength={200}
            value={search}
            onChange={(event) => filter(setSearch, event.target.value)}
          />
          <Select
            label="Statut de la tentative"
            value={status}
            onChange={(event) => filter(setStatus, event.target.value)}
          >
            <option value="">Tous les statuts</option>
            {Object.entries(attemptLabels).map(([key, label]) => (
              <option key={key} value={key}>
                {label}
              </option>
            ))}
          </Select>
          {admin && (
            <>
              {!id && (
                <Select
                  label="Quiz"
                  value={quiz}
                  onChange={(event) => filter(setQuiz, event.target.value)}
                >
                  <option value="">Tous les quiz</option>
                  {quizzes.map((quiz) => (
                    <option key={quiz.id} value={quiz.id}>
                      {quiz.title}
                    </option>
                  ))}
                </Select>
              )}
              <Select
                label="Groupe"
                value={group}
                onChange={(event) => filter(setGroup, event.target.value)}
              >
                <option value="">Tous les groupes</option>
                {groups.map((group) => (
                  <option key={group.id} value={group.id}>
                    {group.name}
                  </option>
                ))}
              </Select>
              <Select
                label="Enseignant"
                value={teacher}
                onChange={(event) => filter(setTeacher, event.target.value)}
              >
                <option value="">Tous les enseignants</option>
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
            Réinitialiser les filtres
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
            Réessayer le chargement
          </button>
        </section>
      ) : (
        <section className="panel">
          <div className="panel-heading">
            <h2>{data.count} tentative(s)</h2>
            <button className="text-button" onClick={reload}>
              Actualiser les résultats
            </button>
          </div>
          {data.results.length ? (
            <div
              className="table-scroll quiz-results-scroll"
              role="region"
              aria-label="Tentatives des étudiants"
              tabIndex={0}
            >
              <table className="quiz-results-table">
                <caption>
                  Tentatives commencées et résultats des étudiants
                </caption>
                <thead>
                  <tr>
                    <th scope="col">Étudiant</th>
                    {!id && <th scope="col">Quiz</th>}
                    <th scope="col">Groupe</th>
                    <th scope="col">Tentative</th>
                    <th scope="col">Statut</th>
                    <th scope="col">Début</th>
                    <th scope="col">Score</th>
                    <th scope="col">Consultation</th>
                  </tr>
                </thead>
                <tbody>
                  {data.results.map((attempt) => (
                    <tr key={attempt.id}>
                      <th scope="row">
                        {personName(attempt.student) || "Étudiant"}
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
                      <td>N° {attempt.number}</td>
                      <td>
                        <Badge>{attemptLabels[attempt.status]}</Badge>
                      </td>
                      <td>{date(attempt.started_at)}</td>
                      <td>
                        {attempt.status === "IN_PROGRESS" ? (
                          <span>En cours</span>
                        ) : (
                          <>
                            <strong>
                              {attempt.points_earned} / {attempt.total_points}
                            </strong>
                            <small className="quiz-result-owner">
                              {attempt.percentage === null
                                ? "Résultat indisponible"
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
                          Voir les réponses
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
                filtered ? "Aucun résultat" : "Aucune tentative pour le moment"
              }
            >
              {filtered
                ? "Aucune tentative ne correspond à vos filtres. Modifiez la recherche ou réinitialisez les filtres."
                : "Les étudiants apparaîtront ici dès qu’ils commenceront une tentative."}
            </Empty>
          )}
          <Pagination page={page} count={data.count} onChange={setPage} />
        </section>
      )}
    </div>
  );
}
