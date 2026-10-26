import { Link, NavLink, Navigate, Outlet, useLocation } from "react-router-dom";
import { useState, useEffect, useRef } from "react";
import { useAuth, destination } from "../auth/AuthContext";
import { Alert, Loading, statuses } from "../components/UI";
import { Brand } from "./FrontOfficeLayout";
export default function AdminLayout() {
  const { user, loading, error, refresh, logout } = useAuth(),
    { pathname } = useLocation();
  const [open, setOpen] = useState(false),
    [logoutError, setLogoutError] = useState<unknown>();
  const sidebarRef = useRef<HTMLElement>(null),
    toggleRef = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    if (open)
      sidebarRef.current?.querySelector<HTMLAnchorElement>("nav a")?.focus();
  }, [open]);
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
  if (user.role !== "ADMIN") return <Navigate to={destination(user)} replace />;
  const base = "/administration",
    home = destination(user);
  const links = [
    [home, "ti-layout-grid2", "Tableau de bord"],
    [base + "/groupes", "ti-folder", "Mes groupes"],
    [base + "/seances", "ti-calendar", "Séances"],
    [base + "/assiduite", "ti-bar-chart", "Assiduité"],
    [base + "/quiz", "ti-help-alt", "Quiz"],
    [base + "/resultats-quiz", "ti-bar-chart", "Résultats des quiz"],
  ];
  links.splice(1, 0, [base + "/utilisateurs", "ti-user", "Utilisateurs"]);
  return (
    <div className="workspace">
      <a className="skip-link" href="#main">
        Aller au contenu
      </a>
      <aside
        ref={sidebarRef}
        id="workspace-nav"
        className={"sidebar " + (open ? "open" : "")}
        onKeyDown={(e) => {
          if (e.key === "Escape") {
            setOpen(false);
            toggleRef.current?.focus();
          }
        }}
      >
        <Brand />
        <p className="sidebar-label">ADMINISTRATION</p>
        <nav aria-label="Navigation de votre espace">
          {links.map(([path, icon, label]) => (
            <NavLink
              onClick={() => setOpen(false)}
              key={path}
              to={path}
              end={path === home}
            >
              <span className={icon} aria-hidden="true" />
              {label}
            </NavLink>
          ))}
          <NavLink to={base + "/profil"} onClick={() => setOpen(false)}>
            <span className="ti-id-badge" aria-hidden="true" />
            Mon profil
          </NavLink>
        </nav>
        <p className="sidebar-label">BIENTÔT DANS LE HUB</p>
        <nav aria-label="Modules en préparation">
          {[
            ["cours", "Cours et ressources"],
            ["resumes", "Résumés et illustrations"],
            ["assistant", "Assistant pédagogique"],
            ["coaching", "Planification et coaching"],
          ].map(([slug, title]) => (
            <NavLink
              key={slug}
              to={base + "/modules/" + slug}
              onClick={() => setOpen(false)}
            >
              {title}
              <span className="soon-dot" aria-label="En préparation" />
            </NavLink>
          ))}
        </nav>
        <div className="sidebar-note">
          <span className="ti-light-bulb" aria-hidden="true" />
          <h3>Avançons ensemble</h3>
          <p>Un espace pour apprendre, un collectif pour progresser.</p>
          <Link to="/">Découvrir le Hub ↗</Link>
        </div>
      </aside>
      <div className="workspace-body">
        <header className="workspace-top">
          <button
            ref={toggleRef}
            aria-controls="workspace-nav"
            className="mobile-toggle"
            aria-expanded={open}
            onClick={() => setOpen(!open)}
          >
            Menu ☰
          </button>
          <p>
            Hub Éducatif Multimodal{" "}
            <span className="top-divider">/ Administration</span>
          </p>
          <details className="profile-menu">
            <summary>
              <span className="avatar">
                {user.avatar ? (
                  <img src={user.avatar} alt="" />
                ) : (
                  user.first_name.charAt(0) + user.last_name.charAt(0)
                )}
              </span>
              <span>
                {user.first_name} {user.last_name}
                <small>{statuses[user.role]}</small>
              </span>
              <span aria-hidden="true">⌄</span>
            </summary>
            <div>
              <Link to={base + "/profil"}>Mon profil</Link>
              <button onClick={() => void logout().catch(setLogoutError)}>
                Se déconnecter
              </button>
            </div>
          </details>
        </header>
        <main id="main" className="workspace-main" key={pathname} tabIndex={-1}>
          <Alert error={logoutError} />
          <Outlet />
        </main>
        <footer className="workspace-footer">
          Nexora · Hub Éducatif Multimodal · Template Eduleb / Bestwpware
        </footer>
      </div>
    </div>
  );
}
