import { useState } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { useResource } from "../hooks/useResource";
import type { Group, Page, Session, Stats, User } from "../api/types";
import { date, query } from "../api/client";
import { Alert, Empty, Loading, Badge, statuses } from "../components/UI";
export default function Dashboard() {
  const { user } = useAuth(),
    base = user!.role === "ADMIN" ? "/administration" : "/espace";
  const [now] = useState(() => new Date().toISOString());
  const groups = useResource<Page<Group>>("groups/"),
    sessions = useResource<Page<Session>>(
      "sessions/?" + query({ from: now, status: "PLANNED" }),
    ),
    stats = useResource<Stats>("statistics/");
  const users = useResource<Page<User>>(
    user!.role === "ADMIN" ? "admin/users/" : "groups/",
  );
  return (
    <>
      <div className="page-heading">
        <div>
          <p className="eyebrow">
            {statuses[user!.role].toUpperCase()} · VOTRE QUOTIDIEN
          </p>
          <h1>
            Bonjour {user!.first_name} <span aria-hidden="true">☀</span>
          </h1>
          <p>Une nouvelle occasion d’apprendre et d’avancer ensemble.</p>
        </div>
        <span className="today">
          {new Intl.DateTimeFormat("fr-FR", {
            dateStyle: "long",
            timeZone: "Africa/Tunis",
          }).format(new Date())}
        </span>
      </div>
      <section className="welcome-panel">
        <div>
          <p className="eyebrow">BIENVENUE DANS LE HUB</p>
          <h2>
            Votre parcours,
            <br />
            au même endroit.
          </h2>
          <p>
            Retrouvez vos groupes et vos prochains rendez-vous.
            <br />
            Chaque séance est un pas de plus.
          </p>
          <Link className="btn_one" to={base + "/seances"}>
            Voir mes séances ↗
          </Link>
        </div>
        <img src="/assets/img/home-img2.png" alt="" />
      </section>
      <div className="metric-grid">
        {[
          [groups.data?.count ?? "—", "Groupes", "ti-folder"],
          [sessions.data?.count ?? "—", "Séances à venir", "ti-calendar"],
          [
            stats.data?.rate == null
              ? "Non calculable"
              : stats.data.rate + " %",
            "Taux de présence",
            "ti-bar-chart",
          ],
          [
            user!.role === "ADMIN"
              ? (users.data?.count ?? "—")
              : (stats.data?.totals.EXCUSED ?? "—"),
            user!.role === "ADMIN" ? "Utilisateurs" : "Absences justifiées",
            "ti-user",
          ],
        ].map(([value, label, icon]) => (
          <div className="metric-card" key={String(label)}>
            <span className={String(icon)} aria-hidden="true" />
            <div>
              <strong>{value}</strong>
              <p>{label}</p>
            </div>
          </div>
        ))}
      </div>
      <div className="dashboard-columns">
        <section className="panel">
          <div className="panel-heading">
            <h2>Prochaines séances</h2>
            <Link to={base + "/seances"}>Tout voir ↗</Link>
          </div>
          <Alert error={sessions.error} />
          {sessions.loading ? (
            <Loading />
          ) : sessions.data?.results.length ? (
            sessions.data.results.slice(0, 4).map((s) => (
              <div key={s.id} className="session-card">
                <span
                  className="calendar-icon ti-calendar"
                  aria-hidden="true"
                />
                <div>
                  <h3>
                    <Link to={base + "/seances/" + s.id}>{s.title}</Link>
                  </h3>
                  <p>
                    {s.group_name} · {date(s.starts_at)}
                  </p>
                  <Badge>{statuses[s.status]}</Badge>
                </div>
              </div>
            ))
          ) : (
            <Empty>
              Aucune séance à venir. Les prochains rendez-vous apparaîtront ici.
            </Empty>
          )}
        </section>
        <section className="panel">
          <div className="panel-heading">
            <h2>Vos groupes</h2>
            <Link to={base + "/groupes"}>Tout voir ↗</Link>
          </div>
          <Alert error={groups.error} />
          <Alert error={stats.error} />
          {groups.loading ? (
            <Loading />
          ) : groups.data?.results.length ? (
            groups.data.results.slice(0, 4).map((g) => (
              <Link
                className="group-mini"
                key={g.id}
                to={base + "/groupes/" + g.id}
              >
                <span className="ti-folder" aria-hidden="true" />
                <div>
                  <h3>{g.name}</h3>
                  <p>
                    {g.code} · {g.level}
                  </p>
                </div>
                <span aria-hidden="true">↗</span>
              </Link>
            ))
          ) : (
            <Empty>Vos groupes seront affichés après votre affectation.</Empty>
          )}
        </section>
      </div>
    </>
  );
}
