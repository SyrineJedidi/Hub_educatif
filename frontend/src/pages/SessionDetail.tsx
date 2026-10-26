import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { api, allPages, date, iso, localDateTime, query } from "../api/client";
import type { Group, Page, Session } from "../api/types";
import { useResource } from "../hooks/useResource";
import {
  Alert,
  Field,
  Select,
  Form,
  Modal,
  Loading,
  Empty,
  Badge,
  Pagination,
  val,
  statuses,
} from "../components/UI";
import SessionForm from "./SessionForm";
export default function SessionDetail() {
  const { id } = useParams(),
    { user } = useAuth(),
    base = user!.role === "ADMIN" ? "/administration" : "/espace";
  const {
    data: s,
    error,
    loading,
    reload,
  } = useResource<Session>("sessions/" + id + "/");
  const [edit, setEdit] = useState(false),
    [cancel, setCancel] = useState(false);
  if (loading) return <Loading />;
  if (!s) return <Alert error={error} />;
  return (
    <>
      <div className="page-heading">
        <div>
          <p className="eyebrow">{s.group_name}</p>
          <h1>{s.title}</h1>
          <Badge>{statuses[s.status]}</Badge>
        </div>
        {user!.role !== "STUDENT" && (
          <div className="actions">
            <button className="btn_one" onClick={() => setEdit(true)}>
              Modifier
            </button>
            {s.status !== "CANCELLED" && (
              <button className="text-button" onClick={() => setCancel(true)}>
                Annuler la séance
              </button>
            )}
          </div>
        )}
      </div>
      <section className="panel">
        <h2>À propos de cette séance</h2>
        <p className="intro">
          {s.description || "Aucune description complémentaire."}
        </p>
        <dl className="session-details">
          <dt>Début</dt>
          <dd>{date(s.starts_at)}</dd>
          <dt>Fin</dt>
          <dd>{date(s.ends_at)}</dd>
          <dt>Lieu ou visioconférence</dt>
          <dd>{s.location || "À préciser"}</dd>
        </dl>
        <p className="field-help">Heure de Tunis · Africa/Tunis</p>
        {user!.role !== "STUDENT" &&
          (s.status === "CANCELLED" ? (
            <>
              <p className="notice">
                La saisie est fermée pour cette séance annulée.
              </p>
              <Link
                className="text-button"
                to={base + "/seances/" + s.id + "/appel"}
              >
                Consulter la feuille historique ↗
              </Link>
            </>
          ) : new Date(s.starts_at) > new Date() ? (
            <p className="notice">
              L’appel sera disponible après le début de la séance.
            </p>
          ) : (
            <Link className="btn_one" to={base + "/seances/" + s.id + "/appel"}>
              Ouvrir la feuille d’appel ↗
            </Link>
          ))}
      </section>
      {edit && (
        <Modal title="Modifier la séance" onClose={() => setEdit(false)}>
          <SessionForm
            session={s}
            onDone={() => {
              setEdit(false);
              reload();
            }}
          />
        </Modal>
      )}
      {cancel && (
        <Modal title="Annuler cette séance ?" onClose={() => setCancel(false)}>
          <p className="intro">
            L’historique sera conservé et cette séance sera exclue des
            statistiques.
          </p>
          <Form
            label="Confirmer l’annulation"
            onSuccess={() => {
              setCancel(false);
              reload();
            }}
            onSubmit={() =>
              api("sessions/" + s.id + "/", "PATCH", {
                group_id: s.group_id,
                title: s.title,
                description: s.description,
                starts_at: s.starts_at,
                ends_at: s.ends_at,
                location: s.location,
                status: "CANCELLED",
              })
            }
          />
        </Modal>
      )}
    </>
  );
}
