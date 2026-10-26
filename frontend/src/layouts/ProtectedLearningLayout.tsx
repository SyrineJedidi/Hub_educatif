import { Navigate, Outlet, useLocation, Link } from "react-router-dom";
import { useAuth, destination } from "../auth/AuthContext";
import { Alert, Loading } from "../components/UI";
import { t } from "../quizzes/i18n";
export default function ProtectedLearningLayout() {
  const { user, loading, error, refresh } = useAuth(),
    { pathname } = useLocation();
  if (loading)
    return (
      <div className="container section-padding">
        <Loading />
      </div>
    );
  if (error)
    return (
      <div className="container section-padding">
        <Alert error={error} />
        <button className="btn_one" onClick={() => void refresh()}>
          {t("Réessayer")}
        </button>
      </div>
    );
  if (!user) return <Navigate to="/connexion" replace />;
  if (user.role === "ADMIN") return <Navigate to={destination(user)} replace />;
  if (
    (pathname === "/espace/enseignant" && user.role !== "TEACHER") ||
    (pathname === "/espace/etudiant" && user.role !== "STUDENT")
  )
    return <Navigate to={destination(user)} replace />;
  if (user.role === "STUDENT" && pathname.endsWith("/appel"))
    return <Navigate to={pathname.slice(0, -6)} replace />;
  return (
    <>
      <div className="learning-trail">
        <div className="container">
          <nav aria-label={t("Fil d’Ariane")}>
            <Link to="/">{t("Accueil")}</Link>
            <span aria-hidden="true"> / </span>
            <Link to={destination(user)}>
              {user.role === "TEACHER"
                ? t("Espace enseignant")
                : t("Mon espace")}
            </Link>
          </nav>
          <span>{t("Vos cours prennent vie. Votre potentiel aussi.")}</span>
        </div>
      </div>
      <div className="front-study">
        <div className="container">
          <Outlet />
        </div>
      </div>
    </>
  );
}
