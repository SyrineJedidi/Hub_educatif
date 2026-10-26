import { useResource } from "../hooks/useResource";
import { useEffect, useRef, useState } from "react";
import { useParams } from "react-router-dom";
import { api, ApiError, date } from "../api/client";
import type { Sheet, Entry, AttendanceStatus, Session } from "../api/types";
import {
  Alert,
  Field,
  Select,
  Loading,
  Empty,
  Modal,
  Form,
  Badge,
  statuses,
} from "../components/UI";
export default function Attendance() {
  const { id } = useParams(),
    [sheet, setSheet] = useState<Sheet | null>(null),
    [entries, setEntries] = useState<Entry[]>([]),
    [error, setError] = useState<unknown>(),
    [busy, setBusy] = useState(false),
    [reason, setReason] = useState(""),
    [message, setMessage] = useState(""),
    [confirm, setConfirm] = useState(false),
    [dirty, setDirty] = useState(false),
    [reloadConfirm, setReloadConfirm] = useState(false);
  const session = useResource<Session>("sessions/" + id + "/");
  const readOnly =
    session.data?.status === "CANCELLED" ||
    (!!session.data && new Date(session.data.starts_at) > new Date());
  const initialized = useRef(false),
    locked = useRef(false);
  async function load() {
    setError(undefined);
    try {
      let d: Sheet;
      try {
        d = await api<Sheet>("sessions/" + id + "/sheet/");
      } catch (e) {
        if (e instanceof ApiError && e.status === 404)
          d = await api<Sheet>("sessions/" + id + "/sheet/", "POST", {});
        else throw e;
      }
      setSheet(d);
      setEntries(d.entries);
      setDirty(false);
    } catch (e) {
      setError(e);
    }
  }
  useEffect(() => {
    if (!initialized.current) {
      initialized.current = true;
      void load();
    }
  }, [id]);
  useEffect(() => {
    const warn = (e: BeforeUnloadEvent) => {
      if (dirty) {
        e.preventDefault();
        e.returnValue = "";
      }
    };
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [dirty]);
  async function save(validate_sheet: boolean) {
    if (locked.current || !sheet) return;
    locked.current = true;
    setBusy(true);
    setError(undefined);
    setMessage("");
    try {
      const d = await api<Sheet>("sessions/" + id + "/sheet/", "PUT", {
        version: sheet.version,
        entries: entries.map(({ student_id, status, comment }) => ({
          student_id,
          status,
          comment,
        })),
        validate_sheet,
        reason,
      });
      setSheet(d);
      setEntries(d.entries);
      setDirty(false);
      setReason("");
      setMessage(validate_sheet ? "Feuille validée." : "Feuille enregistrée.");
    } catch (e) {
      setError(e);
      throw e;
    } finally {
      setBusy(false);
      locked.current = false;
    }
  }
  function update(
    student_id: string,
    key: "status" | "comment",
    value: string,
  ) {
    setEntries((list) =>
      list.map((e) =>
        e.student_id === student_id ? { ...e, [key]: value } : e,
      ),
    );
    setDirty(true);
  }
  return (
    <>
      <div className="page-heading">
        <div>
          <p className="eyebrow">SUIVI PÉDAGOGIQUE</p>
          <h1>Feuille d’appel</h1>
          <p>Vérifiez chaque statut avant d’enregistrer ou de valider.</p>
        </div>
        {sheet && (
          <Badge>
            {sheet.validated ? "Validée" : "Brouillon"} · version{" "}
            {sheet.version}
          </Badge>
        )}
      </div>
      <section className="panel">
        <Alert error={error || session.error} success={message} />
        {readOnly && (
          <p className="notice">
            Consultation de l’historique : la saisie est fermée pour cette
            séance.
          </p>
        )}
        {!sheet ? (
          error ? (
            <button className="btn_one" onClick={() => void load()}>
              Réessayer
            </button>
          ) : (
            <Loading />
          )
        ) : (
          <>
            <div className="panel-heading">
              <h2>
                {entries.length} participant{entries.length > 1 ? "s" : ""}
              </h2>
              <button
                className="text-button"
                disabled={busy || readOnly}
                onClick={() => {
                  setEntries((list) =>
                    list.map((e) => ({ ...e, status: "PRESENT" })),
                  );
                  setDirty(true);
                  setMessage(
                    "Tous les statuts ont été préparés. Vérifiez la feuille puis enregistrez.",
                  );
                }}
              >
                Marquer tous présents
              </button>
            </div>
            <p className="field-help">
              La liste des participants est conservée depuis l’ouverture de
              cette feuille. « Non renseigné » ne compte jamais comme une
              absence.
            </p>
            {entries.length ? (
              <div
                className="table-scroll"
                tabIndex={0}
                role="region"
                aria-label="Tableau à défilement horizontal"
              >
                <table>
                  <thead>
                    <tr>
                      <th>Étudiant</th>
                      <th>Statut</th>
                      <th>Commentaire</th>
                    </tr>
                  </thead>
                  <tbody>
                    {entries.map((e) => (
                      <tr key={e.student_id}>
                        <td>{e.student_name}</td>
                        <td>
                          <Select
                            disabled={readOnly}
                            label={"Statut de " + e.student_name}
                            value={e.status}
                            onChange={(event) =>
                              update(
                                e.student_id,
                                "status",
                                event.target.value as AttendanceStatus,
                              )
                            }
                          >
                            {[
                              "UNSET",
                              "PRESENT",
                              "LATE",
                              "ABSENT",
                              "EXCUSED",
                            ].map((s) => (
                              <option key={s} value={s}>
                                {statuses[s]}
                              </option>
                            ))}
                          </Select>
                        </td>
                        <td>
                          <Field
                            readOnly={readOnly}
                            label={"Commentaire pour " + e.student_name}
                            value={e.comment}
                            maxLength={500}
                            onChange={(event) =>
                              update(
                                e.student_id,
                                "comment",
                                event.target.value,
                              )
                            }
                          />
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <Empty>
                Aucun étudiant n’était inscrit à la date de cette séance.
              </Empty>
            )}
            {sheet.validated && (
              <Field
                label="Motif obligatoire de la correction"
                value={reason}
                maxLength={500}
                onChange={(e) => setReason(e.target.value)}
                required
              />
            )}
            <div className="actions">
              <button
                className="btn_one"
                disabled={busy || readOnly || !entries.length}
                onClick={() => void save(false).catch(() => {})}
              >
                {busy
                  ? "Enregistrement…"
                  : sheet.validated
                    ? "Enregistrer la correction"
                    : "Enregistrer le brouillon"}
              </button>
              {!sheet.validated && (
                <button
                  className="btn_one"
                  disabled={
                    busy ||
                    readOnly ||
                    !entries.length ||
                    entries.some((e) => e.status === "UNSET")
                  }
                  onClick={() => setConfirm(true)}
                >
                  Valider la feuille ↗
                </button>
              )}
              <button
                className="text-button"
                disabled={busy || readOnly}
                onClick={() => (dirty ? setReloadConfirm(true) : void load())}
              >
                Recharger depuis le serveur
              </button>
            </div>
          </>
        )}
      </section>
      {sheet && (
        <section className="panel history-panel">
          <h2>Historique des modifications</h2>
          {sheet.history.length ? (
            <ol>
              {sheet.history
                .slice()
                .reverse()
                .map((h, i) => (
                  <li key={i}>
                    <strong>
                      {
                        sheet.entries.find((e) => e.student_id === h.student_id)
                          ?.student_name
                      }
                    </strong>{" "}
                    · {statuses[h.old_status]} → {statuses[h.new_status]}
                    <p>
                      {date(h.at)} · Auteur :{" "}
                      {h.author_name || "Équipe pédagogique"}
                    </p>
                    {h.old_comment !== h.new_comment && (
                      <p>
                        Commentaire : {h.old_comment || "—"} →{" "}
                        {h.new_comment || "—"}
                      </p>
                    )}
                    <p>{h.reason || "Saisie du brouillon"}</p>
                  </li>
                ))}
            </ol>
          ) : (
            <p>Aucune modification enregistrée.</p>
          )}
        </section>
      )}
      {reloadConfirm && (
        <Modal
          title="Recharger la feuille ?"
          onClose={() => setReloadConfirm(false)}
        >
          <p className="intro">
            Les modifications non enregistrées seront remplacées par la version
            du serveur.
          </p>
          <button
            className="btn_one"
            onClick={() => {
              setReloadConfirm(false);
              void load();
            }}
          >
            Confirmer le rechargement
          </button>
        </Modal>
      )}
      {confirm && (
        <Modal
          title="Valider la feuille d’appel ?"
          onClose={() => setConfirm(false)}
        >
          <p className="intro">
            Après validation, chaque correction exigera un motif. Vous avez
            vérifié les {entries.length} statuts.
          </p>
          <Form
            label="Confirmer la validation"
            onSubmit={async () => {
              await save(true);
              setConfirm(false);
            }}
          />
        </Modal>
      )}
    </>
  );
}
