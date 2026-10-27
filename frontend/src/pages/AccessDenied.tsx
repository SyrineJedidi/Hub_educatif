import { Link } from "react-router-dom";
import { useAuth, destination } from "../auth/AuthContext";
import { statuses } from "../components/UI";
import { useTemplate } from "../layouts/template";
import "../styles/front/portal.css";
/** Shown when a signed-in user opens an area their role does not allow. */
export default function AccessDenied({ area }: { area: string }) {
  useTemplate("front");
  const { user } = useAuth();
  return (
    <main id="main" className="denied" tabIndex={-1}>
      <div className="denied-card" role="alert">
        <span className="denied-icon" aria-hidden="true">
          <span className="ti-lock" />
        </span>
        <p className="denied-code">Erreur 403 · Accès refusé</p>
        <h1>Cet espace ne fait pas partie de vos droits</h1>
        <p>
          <strong>{area}</strong> est réservé à d’autres rôles. Vous êtes connecté
          en tant que <strong>{user ? statuses[user.role] : "visiteur"}</strong>.
        </p>
        <div className="denied-actions">
          <Link className="btn_one" to={user ? destination(user) : "/connexion"}>
            Aller à mon espace
          </Link>
          <Link className="denied-link" to="/">
            Accueil du site
          </Link>
        </div>
      </div>
    </main>
  );
}
