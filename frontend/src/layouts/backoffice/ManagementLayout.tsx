import { Navigate } from "react-router-dom";
import { useAuth } from "../../auth/AuthContext";
import AccessDenied from "../../pages/AccessDenied";
import { Alert, Loading } from "../../components/UI";
import BackOfficeShell from "./BackOfficeShell";
import { modulePaths } from "../../revisions/hooks/useSheetContext";
const paths = modulePaths("TEACHER");
const sections = [
  {
    title: "Résumés et illustrations",
    links: [
      { to: paths.home, icon: "ti-layout-grid2", label: "Vue d’ensemble", end: true },
      { to: paths.sheets, icon: "ti-files", label: "Gestion des fiches" },
      { to: paths.workshop, icon: "ti-wand", label: "Atelier IA" },
      { to: paths.library, icon: "ti-gallery", label: "Médiathèque" },
      { to: paths.followUp, icon: "ti-stats-up", label: "Suivi des étudiants" },
      { to: paths.journal, icon: "ti-list", label: "Journal des générations" },
      { to: paths.stats, icon: "ti-pulse", label: "Statistiques IA" },
    ],
  },
  {
    title: "Mon enseignement",
    links: [
      { to: "/espace/enseignant", icon: "ti-home", label: "Espace enseignant", end: true },
      { to: "/espace/seances", icon: "ti-calendar", label: "Séances et appel" },
      { to: "/espace/quiz", icon: "ti-help-alt", label: "Quiz" },
      { to: "/espace/groupes", icon: "ti-folder", label: "Groupes" },
      { to: "/espace/assistant", icon: "ti-comments", label: "Assistant pédagogique" },
    ],
  },
  {
    title: "Compte",
    links: [
      { to: "/gestion/droits", icon: "ti-key", label: "Mes droits" },
      { to: "/espace/profil", icon: "ti-id-badge", label: "Mon profil" },
    ],
  },
];
/** Teacher back-office of the « Résumés et illustrations » module. */
export default function ManagementLayout() {
  const { user, loading, error, refresh } = useAuth();
  if (loading) return <Loading />;
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
  if (user.role === "ADMIN") return <Navigate to={modulePaths("ADMIN").home} replace />;
  if (user.role !== "TEACHER")
    return <AccessDenied area="Le back-office enseignant" />;
  return <BackOfficeShell area="Enseignant" sections={sections} siteLink="/espace/enseignant" />;
}
