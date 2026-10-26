import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { api, allPages, date, iso, localDateTime, query } from "../api/client";
import type { Group, User, Page, Enrollment } from "../api/types";
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
} from "../components/UI";
import GroupForm from "./GroupForm";
export default function Groups() {
  const { user } = useAuth(),
    base = user!.role === "ADMIN" ? "/administration" : "/espace";
  const [q, setQ] = useState(""),
    [archived, setArchived] = useState(""),
    [page, setPage] = useState(1),
    [create, setCreate] = useState(false);
  const { data, error, loading, reload } = useResource<Page<Group>>(
    "groups/?" + query({ q, archived, page }),
  );
  return (
    <>
      <div className="page-heading">
        <div>
          <p className="eyebrow">APPRENDRE ENSEMBLE</p>
          <h1>
            {user!.role === "ADMIN" ? "Groupes pédagogiques" : "Mes groupes"}
          </h1>
          <p>Un collectif, un enseignant, un parcours partagé.</p>
        </div>
        {user!.role === "ADMIN" && (
          <button className="btn_one" onClick={() => setCreate(true)}>
            Créer un groupe +
          </button>
        )}
      </div>
      <div className="filters">
        <Field
          label="Rechercher un groupe"
          value={q}
          onChange={(e) => {
            setQ(e.target.value);
            setPage(1);
          }}
        />
        <Select
          label="Statut"
          value={archived}
          onChange={(e) => {
            setArchived(e.target.value);
            setPage(1);
          }}
        >
          <option value="">Tous les groupes</option>
          <option value="false">Actifs</option>
          <option value="true">Archivés</option>
        </Select>
      </div>
      <Alert error={error} />
      {loading ? (
        <Loading />
      ) : data?.results.length ? (
        <>
          <div className="cards-grid">
            {data.results.map((g) => (
              <article className="panel group-card" key={g.id}>
                <div className="group-card-top">
                  <span className="ti-folder" aria-hidden="true" />
                  <Badge>{g.archived ? "Archivé" : "Actif"}</Badge>
                </div>
                <p className="eyebrow">
                  {g.code} · {g.academic_year}
                </p>
                <h2>
                  <Link to={base + "/groupes/" + g.id}>{g.name}</Link>
                </h2>
                <p>{g.description || "Un espace pour apprendre ensemble."}</p>
                <div className="group-card-bottom">
                  <p>
                    {g.level}
                    <br />
                    {g.teacher_name}
                  </p>
                  <Link to={base + "/groupes/" + g.id}>Ouvrir ↗</Link>
                </div>
              </article>
            ))}
          </div>
          <Pagination page={page} count={data.count} onChange={setPage} />
        </>
      ) : (
        <Empty>
          Les groupes apparaîtront ici après leur création ou votre inscription.
        </Empty>
      )}
      {create && (
        <Modal title="Créer un groupe" onClose={() => setCreate(false)}>
          <GroupForm
            onDone={() => {
              setCreate(false);
              reload();
            }}
          />
        </Modal>
      )}
    </>
  );
}
