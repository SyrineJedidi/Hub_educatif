import { Suspense } from "react";
import { Navigate, Outlet, useLocation, Link } from "react-router-dom";
import { useAuth, destination } from "../../auth/AuthContext";
import { Alert, Loading } from "../../components/UI";
const sections: Record<string, string> = {
  fiches: "Fiches de révision",
  quiz: "Quiz",
  "resultats-quiz": "Résultats des quiz",
  seances: "Séances",
  assiduite: "Assiduité",
  groupes: "Groupes",
  profil: "Mon profil",
};
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
          Réessayer
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
  const section = sections[pathname.split("/")[2]];
  return (
    <>
      <div className="learning-trail">
        <div className="container">
          <nav aria-label="Fil d’Ariane">
            <Link to="/">Accueil</Link>
            <span aria-hidden="true"> / </span>
            <Link to={destination(user)}>
              {user.role === "TEACHER" ? "Espace enseignant" : "Mon espace"}
            </Link>
            {section && (
              <>
                <span aria-hidden="true"> / </span>
                <span aria-current="page">{section}</span>
              </>
            )}
          </nav>
          <span>Vos cours prennent vie. Votre potentiel aussi.</span>
        </div>
      </div>
      <div className="front-study">
        <div className="container">
          <Suspense fallback={<Loading />}>
            <Outlet />
          </Suspense>
        </div>
      </div>
    </>
  );
}
