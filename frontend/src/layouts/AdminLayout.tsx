import { t } from "../quizzes/i18n";
import { Link, NavLink, Navigate, Outlet, useLocation } from "react-router-dom";
import { useState, useEffect, useRef } from "react";
import { useAuth, destination } from "../auth/AuthContext";
import { Alert, Loading, statuses } from "../components/UI";
import { Brand } from "./FrontOfficeLayout";
import { LanguageSelect } from "../quizzes/i18n";
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
          {t("Réessayer ")}
        </button>
      </div>
    );
  if (!user) return <Navigate to="/connexion" replace />;
  if (user.role !== "ADMIN") return <Navigate to={destination(user)} replace />;
  const base = "/administration",
    home = destination(user);
  const links = [
    [home, "ti-layout-grid2", t("Tableau de bord")],
    [base + "/groupes", "ti-folder", t("Mes groupes")],
    [base + "/seances", "ti-calendar", t("Séances")],
    [base + "/assiduite", "ti-bar-chart", t("Assiduité")],
    [base + "/quiz", "ti-help-alt", t("Quiz")],
    [base + "/resultats-quiz", "ti-bar-chart", t("Résultats des quiz")],
  ];
  links.splice(1, 0, [base + "/utilisateurs", "ti-user", t("Utilisateurs")]);
  return (
    <div className="workspace">
      <a className="skip-link" href="#main">
        {t("Aller au contenu ")}
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
        <p className="sidebar-label">{t("ADMINISTRATION")}</p>
        <nav aria-label={t("Navigation de votre espace")}>
          {links.map(([path, icon, label]) => (
            <NavLink
              onClick={() => setOpen(false)}
              key={path}
              to={path}
              end={path === home}
            >
              <span className={icon} aria-hidden="true" />
              {t(label)}
            </NavLink>
          ))}
          <NavLink to={base + "/profil"} onClick={() => setOpen(false)}>
            <span className="ti-id-badge" aria-hidden="true" />
            {t(" Mon profil ")}
          </NavLink>
        </nav>
        <p className="sidebar-label">{t("BIENTÔT DANS LE HUB")}</p>
        <nav aria-label={t("Modules en préparation")}>
          {[
            ["cours", t("Cours et ressources")],
            ["resumes", t("Résumés et illustrations")],
            ["assistant", t("Assistant pédagogique")],
            ["coaching", t("Planification et coaching")],
          ].map(([slug, title]) => (
            <NavLink
              key={slug}
              to={base + "/modules/" + slug}
              onClick={() => setOpen(false)}
            >
              {title}
              <span className="soon-dot" aria-label={t("En préparation")} />
            </NavLink>
          ))}
        </nav>
        <div className="sidebar-note">
          <span className="ti-light-bulb" aria-hidden="true" />
          <h3>{t("Avançons ensemble")}</h3>
          <p>{t("Un espace pour apprendre, un collectif pour progresser.")}</p>
          <Link to="/">{t("Découvrir le Hub ↗")}</Link>
        </div>
      </aside>
      <div className="workspace-body">
        <header className="workspace-top">
          <LanguageSelect />
          <button
            ref={toggleRef}
            aria-controls="workspace-nav"
            className="mobile-toggle"
            aria-expanded={open}
            onClick={() => setOpen(!open)}
          >
            {t("Menu ☰ ")}
          </button>
          <p>
            Hub Éducatif Multimodal{" "}
            <span className="top-divider">{t("/ Administration")}</span>
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
                <small>{t(statuses[user.role])}</small>
              </span>
              <span aria-hidden="true">⌄</span>
            </summary>
            <div>
              <Link to={base + "/profil"}>{t("Mon profil")}</Link>
              <button onClick={() => void logout().catch(setLogoutError)}>
                {t("Se déconnecter ")}
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
