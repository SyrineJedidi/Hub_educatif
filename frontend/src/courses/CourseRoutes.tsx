import { Link, Navigate, Outlet } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { Alert, Loading } from "../components/UI";
import { useCourseContext } from "./useCourseContext";
import "./courses.css";
export function CourseManagerRoute() {
  const { student, base } = useCourseContext();
  return student ? <Navigate to={base} replace /> : <Outlet />;
}
export function CourseModuleEntry() {
  const { user, loading } = useAuth();
  if (loading) return <Loading />;
  return (
    <Navigate
      to={
        user
          ? user.role === "ADMIN"
            ? "/administration/cours"
            : "/espace/cours"
          : "/connexion"
      }
      replace
    />
  );
}
export function CourseUnavailable({
  title = "Cours indisponible",
  error,
  onRetry,
}: {
  title?: string;
  error: unknown;
  onRetry: () => void;
}) {
  const { base, student } = useCourseContext();
  return (
    <div className="course-module">
      <div className="page-heading">
        <div>
          <p className="eyebrow">COURS ET RESSOURCES</p>
          <h1>{title}</h1>
        </div>
        <Link className="text-button" to={base}>
          {student ? "Tous mes cours" : "Tous les cours"} ↗
        </Link>
      </div>
      <section className="panel">
        <Alert error={error} />
        <button className="text-button" onClick={onRetry}>
          Réessayer le chargement
        </button>
      </section>
    </div>
  );
}
