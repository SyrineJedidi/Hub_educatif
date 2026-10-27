import { Navigate } from "react-router-dom";
import { useAuth } from "../../auth/AuthContext";
import AccessDenied from "../../pages/AccessDenied";
import { Alert, Loading } from "../../components/UI";
import BackOfficeShell from "./BackOfficeShell";
import { modulePaths } from "../../revisions/hooks/useSheetContext";
const base = "/administration";
const revisions = modulePaths("ADMIN");
const sections = [
  {
    title: "Pilotage",
    links: [
      { to: base, icon: "ti-dashboard", label: "Tableau de bord", end: true },
      { to: base + "/utilisateurs", icon: "ti-user", label: "Utilisateurs" },
      { to: base + "/roles", icon: "ti-key", label: "Rôles et permissions" },
    ],
  },
  {
    title: "Organisation pédagogique",
    links: [
      { to: base + "/groupes", icon: "ti-folder", label: "Groupes" },
      { to: base + "/seances", icon: "ti-calendar", label: "Séances" },
      { to: base + "/assiduite", icon: "ti-bar-chart", label: "Assiduité" },
    ],
  },
  {
    title: "Cours et ressources",
    links: [
      { to: base + "/cours", icon: "ti-book", label: "Cours" },
      { to: base + "/matieres", icon: "ti-bookmark-alt", label: "Matières" },
    ],
  },
  {
    title: "Quiz et progression",
    links: [
      { to: base + "/quiz", icon: "ti-help-alt", label: "Quiz" },
      { to: base + "/resultats-quiz", icon: "ti-stats-up", label: "Résultats des quiz" },
    ],
  },
  {
    title: "Résumés et illustrations",
    links: [
      { to: revisions.home, icon: "ti-layout-grid2", label: "Vue d’ensemble" },
      { to: revisions.sheets, icon: "ti-files", label: "Gestion des fiches" },
      { to: revisions.workshop, icon: "ti-wand", label: "Atelier IA" },
      { to: revisions.library, icon: "ti-gallery", label: "Médiathèque" },
      { to: revisions.followUp, icon: "ti-stats-up", label: "Suivi des étudiants" },
      { to: revisions.journal, icon: "ti-list", label: "Journal des générations" },
      { to: revisions.stats, icon: "ti-pulse", label: "Pilotage de l’IA" },
    ],
  },
  {
    title: "Assistant pédagogique",
    links: [
      { to: base + "/assistant", icon: "ti-comments", label: "Assistant", end: true },
      { to: base + "/assistant/signalements", icon: "ti-flag", label: "Signalements" },
    ],
  },
  {
    title: "Planification et coaching",
    links: [{ to: base + "/suivi-revisions", icon: "ti-agenda", label: "Suivi des révisions" }],
  },
  {
    title: "Compte",
    links: [{ to: base + "/profil", icon: "ti-id-badge", label: "Mon profil" }],
  },
];
export default function AdminLayout() {
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
  if (user.role !== "ADMIN")
    return <AccessDenied area="Le back-office d’administration" />;
  return <BackOfficeShell area="Administration" sections={sections} siteLink="/" />;
}
