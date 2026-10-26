import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { allPages, api, query } from "../../api/client";
import { useResource } from "../../hooks/useResource";
import type { Group, Page, User } from "../../api/types";
import { Alert, Empty, Loading, Pagination, Select } from "../../components/UI";
import type { Facets, SheetSummary } from "../types";
import { sheetStatuses } from "../types";
import SheetCard from "../components/SheetCard";
import "../styles/studio.css";
import { useSheetContext } from "../hooks/useSheetContext";
import "../styles/revisions.css";
export default function SheetList() {
  const { base, admin, student, teacher: isTeacher, user, paths } = useSheetContext();
  const [q, setQ] = useState(""),
    [scope, setScope] = useState(""),
    [status, setStatus] = useState(""),
    [course, setCourse] = useState(""),
    [tag, setTag] = useState(""),
    [group, setGroup] = useState(""),
    [teacher, setTeacher] = useState(""),
    [sort, setSort] = useState(""),
    [page, setPage] = useState(1);
  const [groups, setGroups] = useState<Group[]>([]),
    [teachers, setTeachers] = useState<User[]>([]),
    [facets, setFacets] = useState<Facets | null>(null),
    [facetsRevision, setFacetsRevision] = useState(0),
    [sideError, setSideError] = useState<unknown>();
  const { data, error, loading, reload } = useResource<Page<SheetSummary>>(
    "sheets/?" +
      query({ q, scope, status, course, tag, group, teacher, sort, page }),
  );
  const [items, setItems] = useState<SheetSummary[]>([]);
  useEffect(() => setItems(data?.results || []), [data]);
  useEffect(() => {
    api<Facets>("sheets/facets/").then(setFacets).catch(setSideError);
  }, [facetsRevision]);
  useEffect(() => {
    if (!student)
      allPages<Group>("groups/").then(setGroups).catch(setSideError);
    if (admin)
      allPages<User>("admin/users/?role=TEACHER")
        .then(setTeachers)
        .catch(setSideError);
  }, [admin, student]);
  const filtered = !!(
    q ||
    scope ||
    status ||
    course ||
    tag ||
    group ||
    teacher
  );
  const update = (setter: (value: string) => void) => (value: string) => {
    setter(value);
    setPage(1);
  };
  function reset() {
    [
      setQ,
      setScope,
      setStatus,
      setCourse,
      setTag,
      setGroup,
      setTeacher,
    ].forEach((s) => s(""));
    setPage(1);
  }
  const scopes: [string, string][] = student
    ? [
        ["", "Toutes"],
        ["mine", "Mes fiches"],
        ["groups", "Partagées par mes enseignants"],
        ["pinned", "Épinglées"],
      ]
    : [
        ["", "Toutes"],
        ["pinned", "Épinglées"],
      ];
  const stats = facets?.stats;
  return (
    <div className="sheets-module">
      <header className="sheets-hero">
        <div className="sheets-hero-text">
          <p className="eyebrow">RÉSUMÉS ET ILLUSTRATIONS</p>
          <h1>
            {admin
              ? "Fiches de révision"
              : student
                ? "Mes fiches de révision"
                : "Mes fiches pour mes groupes"}
          </h1>
          <p>
            {student
              ? "Retrouvez les fiches partagées par vos enseignants et créez les vôtres : résumés générés avec Gemini, points clés, glossaire et illustrations."
              : "Transformez vos cours en fiches claires : résumé généré avec Gemini et relu par vos soins, points clés, glossaire et illustrations pédagogiques."}
          </p>
          <div className="sheets-hero-actions">
            {isTeacher && (
              <Link className="btn_one" to={paths.home}>
                <span className="ti-settings" aria-hidden="true" /> Gérer mes
                fiches (back-office)
              </Link>
            )}
            <Link className={isTeacher ? "sheets-ghost-button" : "btn_one"} to={paths.workshop}>
              <span className="ti-wand" aria-hidden="true" /> Atelier IA
            </Link>
            <Link className={isTeacher ? "sheets-hero-link" : "sheets-ghost-button"} to={base + "/nouvelle"}>
              <span className="ti-plus" aria-hidden="true" /> Nouvelle fiche
            </Link>
            {admin && (
              <Link className="sheets-hero-link" to={paths.stats}>
                <span className="ti-pulse" aria-hidden="true" /> Pilotage de
                l’IA ↗
              </Link>
            )}
          </div>
        </div>
        <div className="sheets-hero-art" aria-hidden="true">
          <div className="hero-sheet back" />
          <div className="hero-sheet middle" />
          <div className="hero-sheet front">
            <span />
            <span />
            <span />
            <span className="short" />
            <i className="ti-wand" />
          </div>
        </div>
      </header>
      {stats && (
        <dl className="sheets-stats" aria-label="Vue d’ensemble">
          {(
            [
              ["total", "Fiches", "ti-files"],
              student
                ? ["published", "Partagées avec moi", "ti-share"]
                : ["published", "Publiées", "ti-share"],
              [
                "draft",
                student ? "Fiches personnelles" : "Brouillons",
                "ti-pencil-alt",
              ],
              ["ai", "Générées avec Gemini", "ti-wand"],
            ] satisfies [keyof Facets["stats"], string, string][]
          ).map(([key, label, icon]) => (
            <div key={key}>
              <span className={icon} aria-hidden="true" />
              <dt>{label}</dt>
              <dd>{stats[key]}</dd>
            </div>
          ))}
        </dl>
      )}
      <section className="sheets-toolbar" aria-label="Rechercher et filtrer">
        <div className="sheets-scopes" role="group" aria-label="Affichage">
          {scopes.map(([value, label]) => (
            <button
              key={value}
              type="button"
              aria-pressed={scope === value}
              onClick={() => update(setScope)(value)}
            >
              {label}
            </button>
          ))}
        </div>
        <div className="sheets-filter-row">
          <div className="field sheets-search">
            <label htmlFor="sheet-search">Rechercher</label>
            <span className="ti-search" aria-hidden="true" />
            <input
              id="sheet-search"
              className="form-control"
              type="search"
              placeholder="Titre ou cours…"
              value={q}
              maxLength={150}
              onChange={(e) => update(setQ)(e.target.value)}
            />
          </div>
          <Select
            label="Cours"
            value={course}
            onChange={(e) => update(setCourse)(e.target.value)}
          >
            <option value="">Tous les cours</option>
            {facets?.courses.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </Select>
          {!student && (
            <Select
              label="Statut"
              value={status}
              onChange={(e) => update(setStatus)(e.target.value)}
            >
              <option value="">Tous les statuts</option>
              {Object.entries(sheetStatuses).map(([k, v]) => (
                <option key={k} value={k}>
                  {v}
                </option>
              ))}
            </Select>
          )}
          {!student && (
            <Select
              label="Groupe"
              value={group}
              onChange={(e) => update(setGroup)(e.target.value)}
            >
              <option value="">Tous les groupes</option>
              {groups.map((g) => (
                <option key={g.id} value={g.id}>
                  {g.name}
                </option>
              ))}
            </Select>
          )}
          {admin && (
            <Select
              label="Enseignant"
              value={teacher}
              onChange={(e) => update(setTeacher)(e.target.value)}
            >
              <option value="">Tous les enseignants</option>
              {teachers.map((t) => (
                <option key={t.id} value={t.id}>
                  {t.first_name} {t.last_name}
                </option>
              ))}
            </Select>
          )}
          <Select
            label="Trier par"
            value={sort}
            onChange={(e) => update(setSort)(e.target.value)}
          >
            <option value="">Dernière modification</option>
            <option value="created">Date de création</option>
            <option value="title">Titre (A → Z)</option>
          </Select>
        </div>
        {!!facets?.tags.length && (
          <div className="sheets-tags" role="group" aria-label="Étiquettes">
            {facets.tags.slice(0, 14).map((t) => (
              <button
                key={t.name}
                type="button"
                aria-pressed={tag === t.name}
                onClick={() => update(setTag)(tag === t.name ? "" : t.name)}
              >
                #{t.name} <span>{t.count}</span>
              </button>
            ))}
          </div>
        )}
        {filtered && (
          <button className="text-button" type="button" onClick={reset}>
            <span className="ti-close" aria-hidden="true" /> Réinitialiser les
            filtres
          </button>
        )}
      </section>
      <Alert error={error || sideError} />
      {loading && !data ? (
        <Loading />
      ) : items.length ? (
        <>
          <p className="field-help" role="status">
            {data!.count} fiche{data!.count > 1 ? "s" : ""}{" "}
            {filtered ? "correspondant à vos critères" : "dans votre espace"}.
          </p>
          <div className="sheets-grid">
            {items.map((sheet) => (
              <SheetCard
                key={sheet.id}
                sheet={sheet}
                base={base}
                userId={user?.id}
                onPinned={() => {
                  reload();
                  setFacetsRevision((n) => n + 1);
                }}
              />
            ))}
          </div>
          <Pagination page={page} count={data!.count} onChange={setPage} />
        </>
      ) : (
        <section className="panel sheets-empty">
          <Empty
            headingLevel={2}
            title={
              filtered ? "Aucune fiche trouvée" : "Votre bibliothèque est vide"
            }
          >
            {filtered
              ? "Aucune fiche ne correspond à ces critères. Modifiez votre recherche ou réinitialisez les filtres."
              : student
                ? "Vos enseignants n’ont encore rien partagé. Créez votre première fiche personnelle, ou laissez Gemini résumer un cours pour vous."
                : "Collez un cours ou importez un PDF : Gemini prépare le résumé, vous le relisez puis le partagez avec votre groupe."}
          </Empty>
          <div className="sheets-empty-action">
            {filtered ? (
              <button className="btn_one" onClick={reset}>
                Afficher toutes les fiches
              </button>
            ) : (
              <Link className="btn_one" to={paths.workshop}>
                <span className="ti-wand" aria-hidden="true" /> Créer ma
                première fiche
              </Link>
            )}
          </div>
        </section>
      )}
      <Link className="ai-fab" to={paths.workshop}>
        <span className="ai-fab-icon" aria-hidden="true">
          <span className="ti-wand" />
        </span>
        <span className="ai-fab-label">Créer avec l’IA</span>
      </Link>
    </div>
  );
}
