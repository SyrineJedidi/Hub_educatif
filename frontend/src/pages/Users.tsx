import { useState } from "react";
import type { Page, User } from "../api/types";
import { api, date, query } from "../api/client";
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
export default function Users() {
  const [q, setQ] = useState(""),
    [role, setRole] = useState(""),
    [active, setActive] = useState(""),
    [page, setPage] = useState(1),
    [selected, setSelected] = useState<User | null>(null);
  const { data, error, loading, reload } = useResource<Page<User>>(
    "admin/users/?" + query({ q, role, active, page }),
  );
  return (
    <>
      <div className="page-heading">
        <div>
          <p className="eyebrow">ADMINISTRATION</p>
          <h1>Utilisateurs et rôles</h1>
          <p>Accompagnez les membres et gérez leurs accès au Hub.</p>
        </div>
      </div>
      <section className="panel">
        <div className="filters">
          <Field
            label="Rechercher par nom ou email"
            type="search"
            value={q}
            onChange={(e) => {
              setQ(e.target.value);
              setPage(1);
            }}
          />
          <Select
            label="Rôle"
            value={role}
            onChange={(e) => {
              setRole(e.target.value);
              setPage(1);
            }}
          >
            <option value="">Tous les rôles</option>
            {["STUDENT", "TEACHER", "ADMIN"].map((r) => (
              <option key={r} value={r}>
                {statuses[r]}
              </option>
            ))}
          </Select>
          <Select
            label="Statut"
            value={active}
            onChange={(e) => {
              setActive(e.target.value);
              setPage(1);
            }}
          >
            <option value="">Tous les statuts</option>
            <option value="true">Actif</option>
            <option value="false">Inactif</option>
          </Select>
        </div>
        <Alert error={error} />
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
                <caption className="visually-hidden">
                  Utilisateurs du Hub
                </caption>
                <thead>
                  <tr>
                    <th>Membre</th>
                    <th>Rôle</th>
                    <th>Statut</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {data.results.map((u) => (
                    <tr key={u.id}>
                      <td>
                        <strong>
                          {u.first_name} {u.last_name}
                        </strong>
                        <small>{u.email}</small>
                      </td>
                      <td>{statuses[u.role]}</td>
                      <td>
                        <Badge>{u.is_active ? "Actif" : "Inactif"}</Badge>
                      </td>
                      <td>
                        <button
                          className="text-button"
                          onClick={() => setSelected(u)}
                        >
                          Consulter et modifier
                          <span className="visually-hidden">
                            {" "}
                            {u.first_name} {u.last_name}
                          </span>{" "}
                          ↗
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <Pagination page={page} count={data.count} onChange={setPage} />
          </>
        ) : (
          <Empty>Aucun utilisateur ne correspond aux filtres.</Empty>
        )}
      </section>
      {selected && (
        <Modal
          title={selected.first_name + " " + selected.last_name}
          onClose={() => setSelected(null)}
        >
          <p>{selected.email}</p>
          <p className="intro">
            Compte créé le {date(selected.date_joined)}. Dernière connexion :{" "}
            {selected.last_login ? date(selected.last_login) : "Jamais"}.
          </p>
          <Form
            onSubmit={(f) =>
              api("admin/users/" + selected.id + "/", "PATCH", {
                role: val(f, "role"),
                is_active: val(f, "is_active") === "true",
              })
            }
            onSuccess={() => {
              setSelected(null);
              reload();
            }}
          >
            <Select
              name="role"
              label="Rôle attribué"
              defaultValue={selected.role}
            >
              {(selected.role === "ADMIN"
                ? ["ADMIN"]
                : ["STUDENT", "TEACHER"]
              ).map((r) => (
                <option key={r} value={r}>
                  {statuses[r]}
                </option>
              ))}
            </Select>
            <Select
              name="is_active"
              label="Statut du compte"
              defaultValue={String(selected.is_active)}
            >
              <option value="true">Actif</option>
              <option value="false">Inactif</option>
            </Select>
            <p className="field-help">
              Le compte administrateur est unique et son rôle ne peut pas être
              attribué à un autre compte. La désactivation bloque immédiatement
              les accès. L’historique du compte est conservé.
            </p>
          </Form>
        </Modal>
      )}
    </>
  );
}
