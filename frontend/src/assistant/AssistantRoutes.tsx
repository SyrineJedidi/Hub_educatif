import { NavLink, Navigate, Outlet } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { Alert, Loading } from "../components/UI";
import { useAssistantContext } from "./useAssistantContext";
import "./assistant.css";
export function AssistantUserRoute() {
  const { admin, base } = useAssistantContext();
  return admin ? <Navigate to={base} replace /> : <Outlet />;
}
export function AssistantManagerRoute() {
  const { student, chat } = useAssistantContext();
  return student ? <Navigate to={chat} replace /> : <Outlet />;
}
export function AssistantModuleEntry() {
  const { user, loading } = useAuth();
  if (loading) return <Loading />;
  return (
    <Navigate
      to={
        user
          ? user.role === "ADMIN"
            ? "/administration/assistant"
            : "/espace/assistant"
          : "/connexion"
      }
      replace
    />
  );
}
export function AssistantManagerNav() {
  const { admin, student, base } = useAssistantContext();
  if (student) return null;
  const links: [string, string][] = [
    [base, admin ? "Vue d’ensemble" : "Conversations"],
    [base + "/notes", "Notes de cours"],
    [base + "/parametres", "Paramètres"],
    [base + "/suivi", "Suivi"],
    [base + "/signalements", "Signalements"],
  ];
  return (
    <nav className="assistant-manager-nav" aria-label="Pages de l’assistant">
      {links.map(([path, label]) => (
        <NavLink key={path} to={path} end={path === base}>
          {label}
        </NavLink>
      ))}
    </nav>
  );
}
export function AssistantUnavailable({
  title,
  error,
  onRetry,
}: {
  title: string;
  error: unknown;
  onRetry: () => void;
}) {
  return (
    <div className="assistant-module">
      <div className="page-heading">
        <div>
          <p className="eyebrow">ASSISTANT PÉDAGOGIQUE</p>
          <h1>{title}</h1>
        </div>
      </div>
      <AssistantManagerNav />
      <section className="panel" aria-label="Erreur de chargement">
        <Alert error={error} />
        <button className="text-button" onClick={onRetry}>
          Réessayer le chargement
        </button>
      </section>
    </div>
  );
}
