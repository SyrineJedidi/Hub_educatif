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
export default function Sessions() {
  const { user } = useAuth(),
    base = user!.role === "ADMIN" ? "/administration" : "/espace",
    write = user!.role !== "STUDENT";
  const [group, setGroup] = useState(""),
    [status, setStatus] = useState(""),
    [from, setFrom] = useState(""),
    [to, setTo] = useState(""),
    [page, setPage] = useState(1),
    [create, setCreate] = useState(false),
    [groups, setGroups] = useState<Group[]>([]),
    [groupError, setGroupError] = useState<unknown>();
  useEffect(() => {
    allPages<Group>("groups/").then(setGroups).catch(setGroupError);
  }, []);
  const { data, error, loading, reload } = useResource<Page<Session>>(
    "sessions/?" +
      query({
        group,
        status,
        from: from ? iso(from + "T00:00") : "",
        to: to ? iso(to + "T00:00") : "",
        page,
      }),
  );
  return (
    <>
      <div className="page-heading">
        <div>
          <p className="eyebrow">LES RENDEZ-VOUS DU HUB</p>
          <h1>Mes séances</h1>
          <p>Les horaires sont affichés dans le fuseau Africa/Tunis.</p>
        </div>
        {write && (
          <button className="btn_one" onClick={() => setCreate(true)}>
            Créer une séance +
          </button>
        )}
      </div>
      <section className="panel">
        <div className="filters">
          <Select
            label="Groupe"
            value={group}
            onChange={(e) => {
              setGroup(e.target.value);
              setPage(1);
            }}
          >
            <option value="">Tous mes groupes</option>
            {groups.map((g) => (
              <option key={g.id} value={g.id}>
                {g.name}
              </option>
            ))}
          </Select>
          <Select
            label="Statut"
            value={status}
            onChange={(e) => {
              setStatus(e.target.value);
              setPage(1);
            }}
          >
            <option value="">Tous les statuts</option>
            {["PLANNED", "COMPLETED", "CANCELLED"].map((s) => (
              <option key={s} value={s}>
                {statuses[s]}
              </option>
            ))}
          </Select>
          <Field
            label="À partir du"
            type="date"
            value={from}
            onChange={(e) => {
              setFrom(e.target.value);
              setPage(1);
            }}
          />
          <Field
            label="Avant le"
            type="date"
            value={to}
            onChange={(e) => {
              setTo(e.target.value);
              setPage(1);
            }}
          />
        </div>
        <Alert error={error || groupError} />
        {loading ? (
          <Loading />
        ) : data?.results.length ? (
          <>
            <div
              className="table-scroll"
              tabIndex={0}
              role="region"
              aria-label="Tableau à défilement horizontal"
            >
              <table>
                <thead>
                  <tr>
                    <th>Séance</th>
                    <th>Début et fin</th>
                    <th>Statut</th>
                    <th>Action</th>
                  </tr>
                </thead>
                <tbody>
                  {data.results.map((s) => (
                    <tr key={s.id}>
                      <td>
                        <strong>{s.title}</strong>
                        <small>{s.group_name}</small>
                      </td>
                      <td>
                        {date(s.starts_at)}
                        <small>{date(s.ends_at)}</small>
                      </td>
                      <td>
                        <Badge>{statuses[s.status]}</Badge>
                      </td>
                      <td>
                        <Link
                          className="text-button"
                          to={base + "/seances/" + s.id}
                        >
                          Ouvrir
                          <span className="visually-hidden"> {s.title}</span> ↗
                        </Link>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <Pagination page={page} count={data.count} onChange={setPage} />
          </>
        ) : (
          <Empty>Les séances de vos groupes apparaîtront ici.</Empty>
        )}
      </section>
      {create && (
        <Modal title="Créer une séance" onClose={() => setCreate(false)}>
          <SessionForm
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
