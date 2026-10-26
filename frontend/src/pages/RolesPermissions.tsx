import { useAuth } from "../auth/AuthContext";
import type { Role } from "../api/types";
import "../revisions/styles/backoffice.css";
type Access = "yes" | "no" | string;
const roles: [Role, string, string, string][] = [
  ["ADMIN", "Administrateur", "ti-crown", "Gère la plateforme : comptes et rôles, groupes, toutes les fiches, pilotage de l’IA. Travaille uniquement dans le back-office d’administration."],
  ["TEACHER", "Enseignant", "ti-blackboard", "Gère ses groupes et ses contenus : séances, appel, quiz, fiches de révision et IA. Utilise le site et son back-office enseignant."],
  ["STUDENT", "Étudiant", "ti-user", "Consulte ce qui est partagé avec ses groupes, passe les quiz, révise les fiches et crée ses fiches personnelles. Aucun accès au back-office."],
];
const areas: [string, Access, Access, Access][] = [
  ["Site public (accueil, présentation des modules)", "yes", "yes", "yes"],
  ["Espace connecté du site (séances, quiz, fiches)", "Redirigé vers l’administration", "yes", "yes"],
  ["Back-office enseignant (/gestion)", "Redirigé vers l’administration", "yes", "no"],
  ["Back-office d’administration (/administration)", "yes", "no", "no"],
];
const sheetRules: [string, Access, Access, Access][] = [
  ["Lire une fiche publiée de son groupe", "Toutes les fiches", "Ses fiches", "Si inscrit actuellement au groupe"],
  ["Créer une fiche", "Au nom d’un enseignant", "Pour ses groupes", "Fiche personnelle privée"],
  ["Modifier, supprimer", "Toutes", "Ses fiches", "Ses fiches personnelles"],
  ["Publier pour un groupe", "yes", "Après relecture du contenu IA", "no"],
  ["Archiver, restaurer, actions groupées", "yes", "Ses fiches", "no"],
  ["Générer un résumé ou une image avec l’IA", "yes", "20 résumés et 12 images / heure", "Sur ses fiches personnelles"],
  ["Noter un résultat d’IA", "Ses propres générations", "Ses propres générations", "Ses propres générations"],
  ["Réviser avec les cartes mémoire", "Entraînement", "Entraînement", "Progression enregistrée"],
  ["Suivi des lectures des étudiants", "Toutes les fiches", "Ses fiches publiées", "no"],
  ["Journal et statistiques de l’IA", "Toute la plateforme", "Ses générations", "no"],
  ["Médiathèque des illustrations", "Toutes", "Ses fiches", "no"],
];
function Cell({ value }: { value: Access }) {
  if (value === "yes")
    return (
      <span className="rp-yes">
        <span className="ti-check" aria-hidden="true" /> Autorisé
      </span>
    );
  if (value === "no")
    return (
      <span className="rp-no">
        <span className="ti-close" aria-hidden="true" /> Interdit
      </span>
    );
  return <span className="rp-cond">{value}</span>;
}
function Matrix({ title, rows, caption }: { title: string; rows: [string, Access, Access, Access][]; caption: string }) {
  const { user } = useAuth();
  const mine = roles.findIndex(([role]) => role === user?.role);
  return (
    <section className="bo-card" aria-labelledby={"rp-" + title}>
      <h2 className="bo-card-title" id={"rp-" + title}>
        {title}
      </h2>
      <div className="bo-table-wrap">
        <table className="bo-table rp-table">
          <caption className="sr-only">{caption}</caption>
          <thead>
            <tr>
              <th scope="col">Action ou espace</th>
              {roles.map(([role, label], i) => (
                <th scope="col" key={role} className={i === mine ? "rp-mine" : ""}>
                  {label}
                  {i === mine && <span className="rp-you">vous</span>}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map(([action, ...values]) => (
              <tr key={action}>
                <th scope="row" className="bo-cell-main">{action}</th>
                {values.map((value, i) => (
                  <td key={i} data-label={roles[i][1]} className={i === mine ? "rp-mine" : ""}>
                    <Cell value={value} />
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
/** Who can do what: the access rules enforced by the server, shown to everyone. */
export default function RolesPermissions() {
  const { user } = useAuth();
  return (
    <div className="bo-page">
      <header className="bo-page-head">
        <div>
          <p className="bo-eyebrow">Sécurité · Contrôle d’accès</p>
          <h1>Rôles et permissions</h1>
          <p>
            Chaque compte a un seul rôle. Les droits ci-dessous sont vérifiés par le
            serveur à chaque requête : masquer un bouton ne suffit jamais, et une
            adresse saisie à la main vers une ressource interdite répond
            « introuvable ».
          </p>
        </div>
      </header>
      <ul className="rp-roles">
        {roles.map(([role, label, icon, text]) => (
          <li key={role} className={role === user?.role ? "is-mine" : ""}>
            <span className={"rp-role-icon " + icon} aria-hidden="true" />
            <div>
              <h2>
                {label}
                {role === user?.role && <span className="rp-you">votre rôle</span>}
              </h2>
              <p>{text}</p>
            </div>
          </li>
        ))}
      </ul>
      <Matrix title="Accès aux espaces" rows={areas} caption="Espaces accessibles selon le rôle" />
      <Matrix title="Module Résumés et illustrations" rows={sheetRules} caption="Actions autorisées sur les fiches selon le rôle" />
      <section className="bo-card rp-guarantees" aria-labelledby="rp-how">
        <h2 className="bo-card-title" id="rp-how">
          Comment ces règles sont garanties
        </h2>
        <ul>
          <li><span className="ti-lock" aria-hidden="true" /> Session Django protégée par CSRF ; le rôle est relu en base à chaque modification.</li>
          <li><span className="ti-shield" aria-hidden="true" /> Périmètres calculés côté serveur (fiches de l’enseignant, groupes où l’étudiant est inscrit aujourd’hui).</li>
          <li><span className="ti-eye" aria-hidden="true" /> Réponse 404 plutôt que 403 : on ne révèle pas l’existence d’une fiche interdite.</li>
          <li><span className="ti-check-box" aria-hidden="true" /> Chaque règle est couverte par des tests automatisés (python manage.py test revisions).</li>
          <li><span className="ti-timer" aria-hidden="true" /> Limites d’usage de l’IA par utilisateur et par heure.</li>
        </ul>
      </section>
    </div>
  );
}
