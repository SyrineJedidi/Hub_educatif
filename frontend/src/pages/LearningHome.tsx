import { useState } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { useResource } from "../hooks/useResource";
import { date, query } from "../api/client";
import type { Group, Page, Session, Stats } from "../api/types";
import {
  Alert,
  Badge,
  Empty,
  Loading,
  Modal,
  statuses,
} from "../components/UI";
import SessionForm from "./SessionForm";
import { QuizPriorities } from "../quizzes/Progress";
export default function LearningHome() {
  const { user } = useAuth();
  const teacher = user!.role === "TEACHER";
  const [now] = useState(() => new Date().toISOString()),
    [create, setCreate] = useState(false),
    [revision, setRevision] = useState(0);
  const groups = useResource<Page<Group>>("groups/");
  const sessions = useResource<Page<Session>>(
    "sessions/?" + query({ from: now, status: "PLANNED" }),
  );
  const stats = useResource<Stats>("statistics/");
  return (
    <>
      <section className="learning-welcome" aria-labelledby="learning-title">
        <div>
          <p className="eyebrow">VOTRE PARCOURS AVEC NEXORA</p>
          <h1 id="learning-title">
            {teacher ? "Espace enseignant" : "Mon espace"}
          </h1>
          <p className="learning-greeting">
            Bonjour {user!.first_name},{" "}
            {teacher
              ? "accompagnons vos groupes vers leurs prochains objectifs."
              : "heureux de vous retrouver pour la suite de votre parcours."}
          </p>
          <div className="actions">
            {teacher ? (
              <button className="btn_one" onClick={() => setCreate(true)}>
                Créer une séance +
              </button>
            ) : (
              <Link to="/espace/seances" className="btn_one">
                Voir mes séances ↗
              </Link>
            )}
            <Link to="/espace/groupes" className="text-button">
              Retrouver mes groupes ↗
            </Link>
          </div>
        </div>
        <img src="/assets/img/home-img2.webp" alt="" />
      </section>
      {!teacher && <QuizPriorities />}
      <section className="learning-access" aria-label="Accès à vos activités">
        {[
          [
            "ti-folder",
            "Mes groupes",
            "/espace/groupes",
            groups.data
              ? groups.data.count +
                " groupe" +
                (groups.data.count > 1 ? "s" : "") +
                (teacher ? " affecté" + (groups.data.count > 1 ? "s" : "") : "")
              : "Retrouver mon collectif",
          ],
          [
            "ti-calendar",
            teacher ? "Séances et appel" : "Mes séances",
            "/espace/seances",
            sessions.data
              ? sessions.data.count +
                " séance" +
                (sessions.data.count > 1 ? "s" : "") +
                " à venir"
              : "Consulter mes rendez-vous",
          ],
          [
            "ti-bar-chart",
            teacher ? "Assiduité des groupes" : "Mon assiduité",
            "/espace/assiduite",
            stats.data?.rate == null
              ? "Taux non calculable"
              : stats.data.rate + " % de présence",
          ],
        ].map(([icon, title, path, text], i) => (
          <Link className="learning-access-card" to={path} key={path}>
            <span
              className={icon + " sc_" + ["one", "two", "three"][i]}
              aria-hidden="true"
            />
            <div>
              <h2>{title}</h2>
              <p>{text}</p>
            </div>
            <span aria-hidden="true">↗</span>
          </Link>
        ))}
      </section>
      <section className="module-band" aria-labelledby="module-band-title">
        <span className="module-band-icon" aria-hidden="true">
          <span className="ti-wand" />
        </span>
        <div>
          <p className="eyebrow">MODULE RÉSUMÉS ET ILLUSTRATIONS</p>
          <h2 id="module-band-title">
            {teacher
              ? "Préparez vos fiches de révision avec l’IA"
              : "Révisez avec des fiches claires"}
          </h2>
          <p>
            {teacher
              ? "Un cours devient une fiche : résumé, points clés, glossaire et illustration générés, relus par vous, puis partagés avec vos groupes."
              : "Lisez les fiches de vos enseignants, copiez-les dans votre espace ou laissez l’IA résumer vos propres notes."}
          </p>
        </div>
        <div className="module-band-actions">
          {teacher ? (
            <>
              <Link className="btn_one" to="/gestion">
                Gérer mes fiches
              </Link>
              <Link className="module-band-link" to="/gestion/atelier-ia">
                Atelier IA ↗
              </Link>
            </>
          ) : (
            <>
              <Link className="btn_one" to="/espace/fiches">
                Mes fiches de révision
              </Link>
              <Link className="module-band-link" to="/espace/fiches/atelier-ia">
                Atelier IA ↗
              </Link>
            </>
          )}
        </div>
      </section>
      <section className="learning-upcoming panel">
        <div className="panel-heading">
          <div>
            <p className="eyebrow">VOS PROCHAINS RENDEZ-VOUS</p>
            <h2>Prochaines séances</h2>
          </div>
          <Link to="/espace/seances">Toutes mes séances ↗</Link>
        </div>
        <Alert error={sessions.error} />
        {sessions.loading ? (
          <Loading />
        ) : sessions.data?.results.length ? (
          <div className="learning-session-grid">
            {sessions.data.results.slice(0, 4).map((s) => (
              <SessionCard key={s.id} session={s} />
            ))}
          </div>
        ) : (
          <Empty>
            {teacher
              ? "Aucune séance à venir. Vous pouvez préparer la prochaine rencontre de vos groupes."
              : "Aucune séance à venir pour le moment. Vos prochains rendez-vous apparaîtront ici."}
          </Empty>
        )}
      </section>
      <div className="learning-overview">
        <section className="panel">
          <div className="panel-heading">
            <h2>{teacher ? "Mes groupes affectés" : "Mes groupes"}</h2>
            <Link to="/espace/groupes">Tout voir ↗</Link>
          </div>
          <Alert error={groups.error} />
          {groups.loading ? (
            <Loading />
          ) : groups.data?.results.length ? (
            <div>
              {groups.data.results.slice(0, 4).map((g) => (
                <Link
                  className="group-mini"
                  key={g.id}
                  to={"/espace/groupes/" + g.id}
                >
                  <span className="ti-folder" aria-hidden="true" />
                  <div>
                    <h3>{g.name}</h3>
                    <p>
                      {g.code} · {g.level} ·{" "}
                      {g.archived ? "Archivé" : g.academic_year}
                    </p>
                  </div>
                  <span aria-hidden="true">↗</span>
                </Link>
              ))}
            </div>
          ) : (
            <Empty>
              {teacher
                ? "Les groupes qui vous sont affectés apparaîtront ici."
                : "Votre administration vous inscrira dans vos groupes pédagogiques."}
            </Empty>
          )}
        </section>
        <section className="panel learning-attendance">
          <p className="eyebrow">
            {teacher
              ? "ACCOMPAGNER LA PROGRESSION"
              : "LES REPÈRES DE MON PARCOURS"}
          </p>
          <h2>
            {teacher
              ? "Assiduité de mes groupes"
              : "Mon assiduité en un regard"}
          </h2>
          <Alert error={stats.error} />
          {stats.loading ? (
            <Loading />
          ) : (
            stats.data && (
              <>
                <p className="learning-rate">
                  {stats.data.rate == null
                    ? "Non calculable"
                    : stats.data.rate + " %"}
                </p>
                <p className="field-help">
                  {stats.data.rate == null
                    ? "Votre taux sera disponible après la validation des premières feuilles de séances passées."
                    : "Taux de présence sur les feuilles validées des séances passées."}
                </p>
                <dl className="learning-statuses">
                  {["PRESENT", "LATE", "ABSENT", "EXCUSED"].map((status) => (
                    <div key={status}>
                      <dt>{statuses[status]}</dt>
                      <dd>{stats.data!.totals[status]}</dd>
                    </div>
                  ))}
                </dl>
                <Link className="text-button" to="/espace/assiduite">
                  Consulter le suivi détaillé ↗
                </Link>
              </>
            )
          )}
        </section>
      </div>
      {teacher && <TeacherCalls key={revision} now={now} />}
      {create && (
        <Modal title="Créer une séance" onClose={() => setCreate(false)}>
          <SessionForm
            onDone={() => {
              setCreate(false);
              sessions.reload();
              setRevision((n) => n + 1);
            }}
          />
        </Modal>
      )}
    </>
  );
}
function SessionCard({
  session: s,
  call = false,
}: {
  session: Session;
  call?: boolean;
}) {
  return (
    <article className="learning-session">
      <span className="ti-calendar" aria-hidden="true" />
      <p className="eyebrow">{s.group_name}</p>
      <h3>
        <Link to={"/espace/seances/" + s.id}>{s.title}</Link>
      </h3>
      <p>{date(s.starts_at)}</p>
      <p>{s.location || "Lieu à préciser"}</p>
      <Badge>{statuses[s.status]}</Badge>
      <Link
        className="text-button"
        to={"/espace/seances/" + s.id + (call ? "/appel" : "")}
      >
        {call ? "Ouvrir la feuille d’appel" : "Détails de la séance"} ↗
      </Link>
    </article>
  );
}
function TeacherCalls({ now }: { now: string }) {
  const sessions = useResource<Page<Session>>(
    "sessions/?" + query({ to: now }),
  );
  const available =
    sessions.data?.results.filter((s) => s.status !== "CANCELLED") || [];
  return (
    <section className="panel learning-calls">
      <div className="panel-heading">
        <div>
          <p className="eyebrow">LE SUIVI DE VOS RENCONTRES</p>
          <h2>Feuilles d’appel</h2>
        </div>
        <Link to="/espace/seances">Retrouver une séance ↗</Link>
      </div>
      <p className="field-help">
        Ouvrez une séance commencée pour saisir l’appel, enregistrer le
        brouillon ou consulter son historique.
      </p>
      <Alert error={sessions.error} />
      {sessions.loading ? (
        <Loading />
      ) : available.length ? (
        <div className="learning-session-grid">
          {available.slice(0, 4).map((s) => (
            <SessionCard session={s} call key={s.id} />
          ))}
        </div>
      ) : (
        <Empty>
          Aucune séance commencée à afficher. Les feuilles d’appel seront
          accessibles ici après le début de vos séances.
        </Empty>
      )}
    </section>
  );
}
