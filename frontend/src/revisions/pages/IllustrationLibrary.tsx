import { useState } from "react";
import type { FormEvent } from "react";
import { Link } from "react-router-dom";
import { api, date, query } from "../../api/client";
import { useResource } from "../../hooks/useResource";
import type { Page } from "../../api/types";
import { Alert, Loading, Modal, Pagination } from "../../components/UI";
import type { Illustration, SheetStatus } from "../types";
import { StatusPill } from "./SheetTable";
import { useSheetContext } from "../hooks/useSheetContext";
import "../styles/backoffice.css";
interface LibraryItem extends Illustration {
  sheet_title: string;
  sheet_status: SheetStatus;
  course_label: string;
}
type Library = Page<LibraryItem> & { stats: { total: number; AI: number; UPLOAD: number } };
/** Media library: every illustration of the sheets the user manages. */
export default function IllustrationLibrary() {
  const { base, paths } = useSheetContext();
  const [q, setQ] = useState(""),
    [source, setSource] = useState(""),
    [page, setPage] = useState(1),
    [editing, setEditing] = useState<LibraryItem | null>(null),
    [removing, setRemoving] = useState<LibraryItem | null>(null),
    [caption, setCaption] = useState(""),
    [busy, setBusy] = useState(false),
    [actionError, setActionError] = useState<unknown>(),
    [message, setMessage] = useState("");
  const { data, error, loading, reload } = useResource<Library>(
    "revisions/illustrations/?" + query({ q, source, page }),
  );
  async function save(e: FormEvent) {
    e.preventDefault();
    if (!editing) return;
    setBusy(true);
    setActionError(undefined);
    try {
      await api(`sheets/${editing.sheet_id}/illustrations/${editing.id}/`, "PATCH", { caption });
      setEditing(null);
      setMessage("Description mise à jour.");
      reload();
    } catch (err) {
      setActionError(err);
    } finally {
      setBusy(false);
    }
  }
  async function remove() {
    if (!removing) return;
    setBusy(true);
    setActionError(undefined);
    try {
      await api(`sheets/${removing.sheet_id}/illustrations/${removing.id}/`, "DELETE");
      setRemoving(null);
      setMessage("Illustration supprimée.");
      reload();
    } catch (err) {
      setActionError(err);
      setRemoving(null);
    } finally {
      setBusy(false);
    }
  }
  const stats = data?.stats;
  return (
    <div className="bo-page">
      <header className="bo-page-head">
        <div>
          <p className="bo-eyebrow">Résumés et illustrations</p>
          <h1>Médiathèque</h1>
          <p>
            Toutes les illustrations de vos fiches : images importées et images
            générées par l’IA. Corrigez leur description accessible ou supprimez-les.
          </p>
        </div>
        <div className="bo-head-actions">
          <Link className="bo-btn bo-btn-ai" to={paths.workshop}>
            <span className="ti-wand" aria-hidden="true" /> Générer avec l’IA
          </Link>
        </div>
      </header>
      <div className="bo-tabs" role="group" aria-label="Filtrer par origine">
        {[
          ["", "Toutes", stats?.total],
          ["AI", "Générées par l’IA", stats?.AI],
          ["UPLOAD", "Importées", stats?.UPLOAD],
        ].map(([value, label, count]) => (
          <button
            key={String(label)}
            type="button"
            aria-pressed={source === value}
            onClick={() => {
              setSource(String(value));
              setPage(1);
            }}
          >
            {label}
            {count !== undefined && <span className="bo-count">{count}</span>}
          </button>
        ))}
      </div>
      <section className="bo-card" aria-label="Illustrations">
        <div className="bo-toolbar">
          <div className="bo-search">
            <label htmlFor="media-search" className="sr-only">
              Rechercher une illustration
            </label>
            <span className="ti-search" aria-hidden="true" />
            <input
              id="media-search"
              type="search"
              placeholder="Rechercher par description ou fiche…"
              value={q}
              onChange={(e) => {
                setQ(e.target.value);
                setPage(1);
              }}
            />
          </div>
        </div>
        <Alert error={error || actionError} success={message} />
        {loading && !data ? (
          <Loading />
        ) : data?.results.length ? (
          <ul className="media-grid">
            {data.results.map((item) => (
              <li key={item.id} className="media-card">
                <div className="media-thumb">
                  <img src={item.url} alt={item.caption} loading="lazy" width={item.width} height={item.height} />
                  <span className={"media-origin " + (item.source === "AI" ? "is-ai" : "")}>
                    <span className={item.source === "AI" ? "ti-wand" : "ti-upload"} aria-hidden="true" />{" "}
                    {item.source === "AI" ? "IA" : "Importée"}
                  </span>
                </div>
                <div className="media-body">
                  <p className="media-caption">{item.caption}</p>
                  <p className="media-meta">
                    <Link to={base + "/" + item.sheet_id}>{item.sheet_title}</Link>
                    <StatusPill status={item.sheet_status} />
                  </p>
                  <small>
                    {item.width} × {item.height} px · {date(item.created_at)}
                    {item.ai_model && " · " + item.ai_model.split("/").pop()}
                  </small>
                </div>
                {item.sheet_status !== "ARCHIVED" && (
                  <div className="media-actions">
                    <button
                      type="button"
                      className="bo-icon-btn"
                      onClick={() => {
                        setEditing(item);
                        setCaption(item.caption);
                        setMessage("");
                      }}
                      aria-label={"Modifier la description de l’illustration de « " + item.sheet_title + " »"}
                      title="Modifier la description"
                    >
                      <span className="ti-pencil" aria-hidden="true" />
                    </button>
                    <button
                      type="button"
                      className="bo-icon-btn danger"
                      onClick={() => {
                        setRemoving(item);
                        setMessage("");
                      }}
                      aria-label={"Supprimer l’illustration de « " + item.sheet_title + " »"}
                      title="Supprimer"
                    >
                      <span className="ti-trash" aria-hidden="true" />
                    </button>
                  </div>
                )}
              </li>
            ))}
          </ul>
        ) : (
          <div className="bo-empty">
            <span className="ti-gallery" aria-hidden="true" />
            <h2>Aucune illustration</h2>
            <p>Ajoutez des images depuis une fiche ou générez-les avec l’atelier IA.</p>
          </div>
        )}
        {data && (
          <div className="bo-table-foot">
            <span>
              {data.count} illustration{data.count > 1 ? "s" : ""}
            </span>
            <Pagination page={page} count={data.count} onChange={setPage} />
          </div>
        )}
      </section>
      {editing && (
        <Modal title="Modifier la description" onClose={() => !busy && setEditing(null)}>
          <form className="bo-confirm" onSubmit={save}>
            <img className="media-preview" src={editing.url} alt="" />
            <div className="field">
              <label htmlFor="media-caption">Description accessible (lue par les lecteurs d’écran)</label>
              <textarea id="media-caption" className="form-control" rows={3} maxLength={300} value={caption} onChange={(e) => setCaption(e.target.value)} required />
            </div>
            <div className="bo-confirm-actions">
              <button className="bo-btn bo-btn-primary" type="submit" disabled={busy || !caption.trim()}>
                {busy ? "Enregistrement…" : "Enregistrer"}
              </button>
              <button type="button" className="bo-btn" onClick={() => setEditing(null)} disabled={busy}>
                Annuler
              </button>
            </div>
          </form>
        </Modal>
      )}
      {removing && (
        <Modal title="Supprimer cette illustration ?" onClose={() => !busy && setRemoving(null)}>
          <div className="bo-confirm">
            <p>
              L’image sera retirée de la fiche « {removing.sheet_title} » et
              effacée définitivement.
            </p>
            <div className="bo-confirm-actions">
              <button type="button" className="bo-btn bo-btn-danger-solid" onClick={() => void remove()} disabled={busy}>
                {busy ? "Suppression…" : "Supprimer"}
              </button>
              <button type="button" className="bo-btn" onClick={() => setRemoving(null)} disabled={busy}>
                Annuler
              </button>
            </div>
          </div>
        </Modal>
      )}
    </div>
  );
}
