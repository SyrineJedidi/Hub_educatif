import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { allPages, api, date, query } from "../../api/client";
import { useResource } from "../../hooks/useResource";
import type { Group, Page, User } from "../../api/types";
import { Alert, Loading, Modal, Pagination } from "../../components/UI";
import type { Facets, SheetStatus, SheetSummary } from "../types";
import { sheetStatuses } from "../types";
import { useSheetContext } from "../hooks/useSheetContext";
import "../styles/backoffice.css";
type BulkAction = "publish" | "unpublish" | "archive" | "delete";
interface BulkResult {
  done: string[];
  failed: { id: string; title: string; reason: string }[];
}
const bulkLabels: Record<BulkAction, [string, string, string]> = {
  publish: ["Publier", "ti-share", "publiée(s)"],
  unpublish: ["Repasser en brouillon", "ti-back-left", "repassée(s) en brouillon"],
  archive: ["Archiver", "ti-archive", "archivée(s)"],
  delete: ["Supprimer", "ti-trash", "supprimée(s)"],
};
export function StatusPill({ status }: { status: SheetStatus }) {
  return (
    <span className={"bo-pill status-" + status.toLowerCase()}>
      {sheetStatuses[status]}
    </span>
  );
}
export function AiPill({ sheet }: { sheet: SheetSummary }) {
  if (!sheet.ai_generated) return <span className="bo-muted">Manuelle</span>;
  return sheet.ai_reviewed ? (
    <span className="bo-pill ai-reviewed">
      <span className="ti-check" aria-hidden="true" /> IA relue
    </span>
  ) : (
    <span className="bo-pill ai-pending">
      <span className="ti-alert" aria-hidden="true" /> IA à relire
    </span>
  );
}
/** Back-office table: create, read, update and delete sheets, one by one or in bulk. */
export default function SheetTable() {
  const { base, admin, paths } = useSheetContext();
  const navigate = useNavigate();
  const [q, setQ] = useState(""),
    [status, setStatus] = useState(""),
    [course, setCourse] = useState(""),
    [group, setGroup] = useState(""),
    [teacher, setTeacher] = useState(""),
    [sort, setSort] = useState(""),
    [page, setPage] = useState(1),
    [selected, setSelected] = useState<string[]>([]),
    [confirm, setConfirm] = useState<{ action: BulkAction; ids: string[] } | null>(null),
    [busy, setBusy] = useState(false),
    [result, setResult] = useState<(BulkResult & { action: BulkAction }) | null>(null),
    [actionError, setActionError] = useState<unknown>();
  const [groups, setGroups] = useState<Group[]>([]),
    [teachers, setTeachers] = useState<User[]>([]),
    [facets, setFacets] = useState<Facets | null>(null),
    [revision, setRevision] = useState(0);
  const { data, error, loading, reload } = useResource<Page<SheetSummary>>(
    "sheets/?" + query({ q, status, course, group, teacher, sort, page }),
  );
  useEffect(() => {
    api<Facets>("sheets/facets/").then(setFacets).catch(setActionError);
  }, [revision]);
  useEffect(() => {
    allPages<Group>("groups/").then(setGroups).catch(setActionError);
    if (admin)
      allPages<User>("admin/users/?role=TEACHER").then(setTeachers).catch(setActionError);
  }, [admin]);
  useEffect(() => setSelected([]), [data]);
  const rows = data?.results || [];
  const update = (setter: (v: string) => void) => (value: string) => {
    setter(value);
    setPage(1);
  };
  const refresh = () => {
    reload();
    setRevision((n) => n + 1);
  };
  const allChecked = rows.length > 0 && rows.every((r) => selected.includes(r.id));
  function toggle(id: string) {
    setSelected((s) => (s.includes(id) ? s.filter((x) => x !== id) : [...s, id]));
  }
  async function run(action: BulkAction, ids: string[]) {
    setBusy(true);
    setActionError(undefined);
    try {
      const outcome = await api<BulkResult>("sheets/bulk/", "POST", { action, ids });
      setResult({ ...outcome, action });
      setConfirm(null);
      refresh();
    } catch (err) {
      setActionError(err);
    } finally {
      setBusy(false);
    }
  }
  async function duplicate(sheet: SheetSummary) {
    setActionError(undefined);
    try {
      const copy = await api<SheetSummary>("sheets/" + sheet.id + "/duplicate/", "POST", {});
      navigate(base + "/" + copy.id + "/modifier");
    } catch (err) {
      setActionError(err);
    }
  }
  const stats = facets?.stats;
  const tabs: [string, string, number | undefined][] = [
    ["", "Toutes", stats?.total],
    ["DRAFT", "Brouillons", stats?.draft],
    ["PUBLISHED", "Publiées", stats?.published],
    ["ARCHIVED", "Archivées", stats?.archived],
  ];
  return (
    <div className="bo-page">
      <header className="bo-page-head">
        <div>
          <p className="bo-eyebrow">Résumés et illustrations</p>
          <h1>Gestion des fiches</h1>
          <p>
            Créez, modifiez, publiez, archivez ou supprimez les fiches de révision
            {admin ? " de tous les enseignants." : " de vos groupes."} Cochez
            plusieurs fiches pour agir sur toutes en une fois.
          </p>
        </div>
        <div className="bo-head-actions">
          <Link className="bo-btn bo-btn-primary" to={base + "/nouvelle"}>
            <span className="ti-plus" aria-hidden="true" /> Nouvelle fiche
          </Link>
          <Link className="bo-btn bo-btn-ai" to={paths.workshop}>
            <span className="ti-wand" aria-hidden="true" /> Créer avec l’IA
          </Link>
        </div>
      </header>
      <div className="bo-tabs" role="group" aria-label="Filtrer par statut">
        {tabs.map(([value, label, count]) => (
          <button
            key={label}
            type="button"
            aria-pressed={status === value}
            onClick={() => update(setStatus)(value)}
          >
            {label}
            {count !== undefined && <span className="bo-count">{count}</span>}
          </button>
        ))}
      </div>
      <section className="bo-card" aria-label="Liste des fiches">
        <div className="bo-toolbar">
          <div className="bo-search">
            <label htmlFor="sheet-search" className="sr-only">
              Rechercher une fiche
            </label>
            <span className="ti-search" aria-hidden="true" />
            <input
              id="sheet-search"
              type="search"
              placeholder="Rechercher par titre ou cours…"
              value={q}
              onChange={(e) => update(setQ)(e.target.value)}
            />
          </div>
          <label className="bo-filter">
            <span>Cours</span>
            <select value={course} onChange={(e) => update(setCourse)(e.target.value)}>
              <option value="">Tous</option>
              {facets?.courses.map((c) => (
                <option key={c}>{c}</option>
              ))}
            </select>
          </label>
          <label className="bo-filter">
            <span>Groupe</span>
            <select value={group} onChange={(e) => update(setGroup)(e.target.value)}>
              <option value="">Tous</option>
              {groups.map((g) => (
                <option key={g.id} value={g.id}>
                  {g.name}
                </option>
              ))}
            </select>
          </label>
          {admin && (
            <label className="bo-filter">
              <span>Enseignant</span>
              <select value={teacher} onChange={(e) => update(setTeacher)(e.target.value)}>
                <option value="">Tous</option>
                {teachers.map((t) => (
                  <option key={t.id} value={t.id}>
                    {t.first_name} {t.last_name}
                  </option>
                ))}
              </select>
            </label>
          )}
          <label className="bo-filter">
            <span>Tri</span>
            <select value={sort} onChange={(e) => update(setSort)(e.target.value)}>
              <option value="">Dernière modification</option>
              <option value="created">Date de création</option>
              <option value="title">Titre (A → Z)</option>
            </select>
          </label>
        </div>
        {selected.length > 0 && (
          <div className="bo-bulk" role="region" aria-label="Actions groupées">
            <strong>
              {selected.length} fiche{selected.length > 1 ? "s" : ""} sélectionnée
              {selected.length > 1 ? "s" : ""}
            </strong>
            <div>
              {(Object.keys(bulkLabels) as BulkAction[]).map((action) => (
                <button
                  key={action}
                  type="button"
                  className={"bo-btn bo-btn-small" + (action === "delete" ? " bo-btn-danger" : "")}
                  onClick={() =>
                    action === "delete" || action === "archive"
                      ? setConfirm({ action, ids: selected })
                      : void run(action, selected)
                  }
                  disabled={busy}
                >
                  <span className={bulkLabels[action][1]} aria-hidden="true" />{" "}
                  {bulkLabels[action][0]}
                </button>
              ))}
              <button type="button" className="bo-link-button" onClick={() => setSelected([])}>
                Annuler la sélection
              </button>
            </div>
          </div>
        )}
        <Alert error={error || actionError} />
        {result && (
          <div className={"notice" + (result.failed.length ? " bo-notice-warn" : "")} role="status">
            <strong>
              {result.done.length} fiche{result.done.length > 1 ? "s" : ""}{" "}
              {bulkLabels[result.action][2]}.
            </strong>
            {result.failed.length > 0 && (
              <ul className="bo-failures">
                {result.failed.map((f) => (
                  <li key={f.id}>
                    <strong>{f.title || "Fiche inaccessible"}</strong> : {f.reason}
                  </li>
                ))}
              </ul>
            )}
            <button type="button" className="bo-link-button" onClick={() => setResult(null)}>
              Fermer
            </button>
          </div>
        )}
        {loading && !data ? (
          <Loading />
        ) : rows.length ? (
          <div className="bo-table-wrap">
            <table className="bo-table has-check">
              <caption className="sr-only">
                Fiches de révision, {data?.count} au total
              </caption>
              <thead>
                <tr>
                  <th scope="col" className="bo-check">
                    <input
                      type="checkbox"
                      aria-label="Sélectionner toutes les fiches de la page"
                      checked={allChecked}
                      onChange={() => setSelected(allChecked ? [] : rows.map((r) => r.id))}
                    />
                  </th>
                  <th scope="col">Fiche</th>
                  <th scope="col">Groupe</th>
                  {admin && <th scope="col">Enseignant</th>}
                  <th scope="col">Statut</th>
                  <th scope="col">Contenu IA</th>
                  <th scope="col" className="bo-num">Images</th>
                  <th scope="col">Mise à jour</th>
                  <th scope="col" className="bo-actions-col">Actions</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((sheet) => (
                  <tr key={sheet.id} className={selected.includes(sheet.id) ? "is-selected" : ""}>
                    <td className="bo-check">
                      <input
                        type="checkbox"
                        aria-label={"Sélectionner « " + sheet.title + " »"}
                        checked={selected.includes(sheet.id)}
                        onChange={() => toggle(sheet.id)}
                      />
                    </td>
                    <td data-label="Fiche" className="bo-cell-main">
                      <Link className="bo-row-title" to={base + "/" + sheet.id}>
                        {sheet.pinned && (
                          <span className="ti-pin2" aria-label="Épinglée" />
                        )}{" "}
                        {sheet.title}
                      </Link>
                      <small>{sheet.course_label}</small>
                    </td>
                    <td data-label="Groupe">
                      {sheet.learning_group_name || <span className="bo-muted">Personnelle</span>}
                    </td>
                    {admin && <td data-label="Enseignant">{sheet.owner_name}</td>}
                    <td data-label="Statut">
                      <StatusPill status={sheet.status} />
                    </td>
                    <td data-label="Contenu IA">
                      <AiPill sheet={sheet} />
                    </td>
                    <td data-label="Images" className="bo-num">
                      {sheet.illustration_count}
                    </td>
                    <td data-label="Mise à jour">
                      <time dateTime={sheet.updated_at}>{date(sheet.updated_at)}</time>
                    </td>
                    <td className="bo-actions-col">
                      <div className="bo-row-actions">
                        <Link
                          className="bo-icon-btn"
                          to={base + "/" + sheet.id}
                          aria-label={"Consulter « " + sheet.title + " »"}
                          title="Consulter"
                        >
                          <span className="ti-eye" aria-hidden="true" />
                        </Link>
                        {sheet.status !== "ARCHIVED" && (
                          <Link
                            className="bo-icon-btn"
                            to={base + "/" + sheet.id + "/modifier"}
                            aria-label={"Modifier « " + sheet.title + " »"}
                            title="Modifier"
                          >
                            <span className="ti-pencil" aria-hidden="true" />
                          </Link>
                        )}
                        <button
                          type="button"
                          className="bo-icon-btn"
                          onClick={() => void duplicate(sheet)}
                          aria-label={"Dupliquer « " + sheet.title + " »"}
                          title="Dupliquer"
                        >
                          <span className="ti-layers" aria-hidden="true" />
                        </button>
                        <button
                          type="button"
                          className="bo-icon-btn danger"
                          onClick={() => setConfirm({ action: "delete", ids: [sheet.id] })}
                          disabled={sheet.status === "PUBLISHED"}
                          aria-label={"Supprimer « " + sheet.title + " »"}
                          title={
                            sheet.status === "PUBLISHED"
                              ? "Retirez la fiche de la publication avant de la supprimer"
                              : "Supprimer"
                          }
                        >
                          <span className="ti-trash" aria-hidden="true" />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="bo-empty">
            <span className="ti-files" aria-hidden="true" />
            <h2>{q || status || course || group || teacher ? "Aucune fiche ne correspond" : "Aucune fiche pour l’instant"}</h2>
            <p>
              Créez votre première fiche à la main ou laissez l’IA la préparer à
              partir d’un cours.
            </p>
            <Link className="bo-btn bo-btn-ai" to={paths.workshop}>
              <span className="ti-wand" aria-hidden="true" /> Ouvrir l’atelier IA
            </Link>
          </div>
        )}
        {data && (
          <div className="bo-table-foot">
            <span>
              {data.count} fiche{data.count > 1 ? "s" : ""}
            </span>
            <Pagination page={page} count={data.count} onChange={setPage} />
          </div>
        )}
      </section>
      {confirm && (
        <Modal
          title={
            confirm.action === "delete"
              ? "Supprimer définitivement ?"
              : "Archiver les fiches ?"
          }
          onClose={() => !busy && setConfirm(null)}
        >
          <div className="bo-confirm">
            <p>
              {confirm.action === "delete"
                ? `${confirm.ids.length} fiche${confirm.ids.length > 1 ? "s" : ""} et leurs illustrations seront effacées. Cette action est irréversible. Les fiches publiées doivent d’abord être retirées.`
                : `${confirm.ids.length} fiche${confirm.ids.length > 1 ? "s" : ""} passeront en lecture seule et ne seront plus visibles par les étudiants.`}
            </p>
            <div className="bo-confirm-actions">
              <button
                type="button"
                className={"bo-btn " + (confirm.action === "delete" ? "bo-btn-danger-solid" : "bo-btn-primary")}
                onClick={() => void run(confirm.action, confirm.ids)}
                disabled={busy}
              >
                {busy ? "Traitement…" : bulkLabels[confirm.action][0]}
              </button>
              <button type="button" className="bo-btn" onClick={() => setConfirm(null)} disabled={busy}>
                Annuler
              </button>
            </div>
          </div>
        </Modal>
      )}
    </div>
  );
}
