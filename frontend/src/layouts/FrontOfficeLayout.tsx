import { t } from "../quizzes/i18n";
import { useEffect, useRef, useState } from "react";
import { Link, NavLink, Outlet, useLocation } from "react-router-dom";
import { useAuth, destination } from "../auth/AuthContext";
import { Alert, statuses } from "../components/UI";
import "../styles/front-office.css";
import { LanguageSelect } from "../quizzes/i18n";
export function Brand() {
  return (
    <Link
      className="brand"
      to="/"
      aria-label="Hub Éducatif Multimodal — accueil"
    >
      <span className="ti-book" aria-hidden="true" />
      <span>
        Hub Éducatif<small>Multimodal · Nexora</small>
      </span>
    </Link>
  );
}
export default function FrontOfficeLayout() {
  const { user, logout } = useAuth();
  const { pathname } = useLocation();
  const [open, setOpen] = useState(false),
    [error, setError] = useState<unknown>();
  const header = useRef<HTMLElement>(null),
    toggle = useRef<HTMLButtonElement>(null),
    nav = useRef<HTMLElement>(null);
  const base = user?.role === "ADMIN" ? "/administration" : "/espace";
  const spaceLabel =
    user?.role === "TEACHER"
      ? t("Espace enseignant")
      : user?.role === "ADMIN"
        ? t("Administration")
        : t("Mon espace");
  const closeMenus = () =>
    header.current
      ?.querySelectorAll("details[open]")
      .forEach((d) => d.removeAttribute("open"));
  useEffect(() => {
    setOpen(false);
    closeMenus();
  }, [pathname]);
  useEffect(() => {
    const outside = (e: PointerEvent) => {
      if (!header.current?.contains(e.target as Node)) {
        setOpen(false);
        closeMenus();
      }
    };
    document.addEventListener("pointerdown", outside);
    return () => document.removeEventListener("pointerdown", outside);
  }, []);
  function toggleNavigation() {
    if (!open) {
      setOpen(true);
      requestAnimationFrame(() =>
        nav.current?.querySelector<HTMLAnchorElement>("a")?.focus(),
      );
    } else setOpen(false);
  }
  return (
    <div className="front-office">
      <a className="skip-link" href="#main">
        {t("Aller au contenu ")}
      </a>
      <header
        ref={header}
        id="navigation"
        className={
          "navbar-light bg-faded site-navigation front-header" +
          (user ? " is-connected" : "")
        }
        onKeyDown={(e) => {
          if (e.key === "Escape") {
            const detail = (e.target as HTMLElement).closest("details[open]");
            if (detail) {
              detail.removeAttribute("open");
              detail.querySelector<HTMLElement>("summary")?.focus();
            } else if (open) {
              setOpen(false);
              toggle.current?.focus();
            }
          }
        }}
      >
        <div className="container-fluid hub-header">
          <LanguageSelect />
          <Brand />
          <nav
            ref={nav}
            id="public-nav"
            className={open ? "public-nav open" : "public-nav"}
            aria-label={t("Navigation principale")}
            onClick={(e) => {
              if ((e.target as HTMLElement).closest("a")) {
                setOpen(false);
                closeMenus();
              }
            }}
          >
            <NavLink to="/" end>
              {t("Accueil ")}
            </NavLink>
            {user ? (
              <>
                <NavLink to={destination(user)}>{spaceLabel}</NavLink>
                {user.role !== "ADMIN" && (
                  <details className="front-dropdown">
                    <summary>
                      {t("Mes activités ")}
                      <span aria-hidden="true">⌄</span>
                    </summary>
                    <div>
                      <NavLink to="/espace/quiz">
                        {user.role === "TEACHER"
                          ? t("Mes quiz")
                          : t("Quiz de mes groupes")}
                      </NavLink>
                      <NavLink to="/espace/groupes">{t("Mes groupes")}</NavLink>
                      <NavLink to="/espace/seances">
                        {user.role === "TEACHER"
                          ? t("Séances et feuilles d’appel")
                          : t("Mes séances")}
                      </NavLink>
                      <NavLink to="/espace/assiduite">
                        {user.role === "TEACHER"
                          ? t("Assiduité de mes groupes")
                          : t("Mon assiduité")}
                      </NavLink>
                    </div>
                  </details>
                )}
                <details className="front-dropdown">
                  <summary>
                    {t("Les modules ")}
                    <span aria-hidden="true">⌄</span>
                  </summary>
                  <div>
                    {[
                      ["cours", t("Cours et ressources")],
                      ["resumes", t("Résumés et illustrations")],
                      ["assistant", t("Assistant pédagogique")],
                      ["quiz", t("Quiz et progression")],
                      ["coaching", t("Planification et coaching")],
                    ].map(([slug, label]) => (
                      <Link
                        key={slug}
                        to={
                          slug === "quiz"
                            ? user.role === "ADMIN"
                              ? "/administration/quiz"
                              : "/espace/quiz"
                            : "/modules/" + slug
                        }
                      >
                        {t(label)}
                        <small>
                          {slug === "quiz"
                            ? t("Quiz, tentatives et correction")
                            : t("En préparation")}
                        </small>
                      </Link>
                    ))}
                  </div>
                </details>
              </>
            ) : (
              <>
                <a href="/#parcours">{t("Notre approche")}</a>
                <a href="/#modules">{t("Les modules")}</a>
                <a href="/#nexora">Nexora</a>
                <Link className="header-btn" to="/connexion">
                  {t("Connexion ")}
                </Link>
                <Link className="btn_one" to="/inscription">
                  {t("S’inscrire ")}
                  <span aria-hidden="true">↗</span>
                </Link>
              </>
            )}
          </nav>
          {user && (
            <details className="profile-menu front-profile">
              <summary
                aria-label={
                  t("Menu de profil de ") +
                  user.first_name +
                  " " +
                  user.last_name
                }
              >
                <span className="avatar">
                  {user.avatar ? (
                    <img src={user.avatar} alt="" />
                  ) : (
                    user.first_name.charAt(0) + user.last_name.charAt(0)
                  )}
                </span>
                <span className="front-profile-name">
                  {user.first_name} {user.last_name}
                  <small>{t(statuses[user.role])}</small>
                </span>
                <span aria-hidden="true">⌄</span>
              </summary>
              <div>
                <Link
                  to={base + "/profil"}
                  onClick={() => {
                    setOpen(false);
                    closeMenus();
                  }}
                >
                  {t("Mon profil ")}
                </Link>
                <button onClick={() => void logout().catch(setError)}>
                  {t("Se déconnecter ")}
                </button>
              </div>
            </details>
          )}
          <button
            ref={toggle}
            className="mobile-toggle"
            aria-expanded={open}
            aria-controls="public-nav"
            onClick={toggleNavigation}
          >
            {t("Menu ")}
            <span aria-hidden="true">☰</span>
          </button>
        </div>
      </header>
      {!!error && (
        <div className="container">
          <Alert error={error} />
        </div>
      )}
      <main id="main" tabIndex={-1}>
        <Outlet />
      </main>
      <Footer />
    </div>
  );
}
export function Footer() {
  const { user } = useAuth();
  const base = user?.role === "ADMIN" ? "/administration" : "/espace";
  const learning = user ? base : "/connexion";
  return (
    <footer>
      <div className="footer section-padding">
        <div className="container">
          <div className="row">
            <div className="col-lg-3 col-sm-6">
              <div className="single_footer">
                <Brand />
                <p>
                  {t(
                    "Vos cours prennent vie. Votre potentiel aussi. Un projet académique porté par l’équipe Nexora. ",
                  )}
                </p>
              </div>
            </div>
            <div className="col-lg-2 col-sm-6">
              <div className="single_footer">
                <h2>{t("Votre espace")}</h2>
                <ul>
                  <li>
                    <Link to={user ? destination(user) : "/connexion"}>
                      {user ? t("Mon espace") : t("Se connecter")}
                    </Link>
                  </li>
                  <li>
                    <Link to={user ? base + "/profil" : "/inscription"}>
                      {user ? t("Mon profil") : t("Créer un compte")}
                    </Link>
                  </li>
                  <li>
                    <Link to="/mot-de-passe-oublie">
                      {t("Mot de passe oublié")}
                    </Link>
                  </li>
                </ul>
              </div>
            </div>
            <div className="col-lg-2 col-sm-6">
              <div className="single_footer">
                <h2>{t("Au quotidien")}</h2>
                <ul>
                  <li>
                    <Link to={user ? learning + "/groupes" : learning}>
                      {t("Mes groupes ")}
                    </Link>
                  </li>
                  <li>
                    <Link to={user ? learning + "/seances" : learning}>
                      {t("Mes séances ")}
                    </Link>
                  </li>
                  <li>
                    <Link to={user ? learning + "/assiduite" : learning}>
                      {t("Mon assiduité ")}
                    </Link>
                  </li>
                </ul>
              </div>
            </div>
            <div className="col-lg-3 col-sm-6">
              <div className="single_footer">
                <h2>{t("Apprendre autrement")}</h2>
                <ul>
                  <li>
                    <Link to="/modules/cours">{t("Cours et ressources")}</Link>
                  </li>
                  <li>
                    <Link to="/modules/assistant">
                      {t("Assistant pédagogique")}
                    </Link>
                  </li>
                  <li>
                    <Link to="/modules/quiz">{t("Quiz et progression")}</Link>
                  </li>
                </ul>
              </div>
            </div>
            <div className="col-lg-2 col-sm-6">
              <div className="single_footer">
                <h2>Nexora</h2>
                <p>
                  {t(
                    "Cinq membres, une ambition : rapprocher apprentissage et accompagnement. ",
                  )}
                </p>
              </div>
            </div>
          </div>
        </div>
      </div>
      <div className="foot_copy">
        <div className="footer_copyright">
          <p>
            Hub Éducatif Multimodal · Équipe Nexora
            <br />
            Template © 2024 <a href="https://bestwpware.com/">Bestwpware</a>
            {t(" · Distribution ")}
            <a href="https://themewagon.com/">ThemeWagon</a>
          </p>
        </div>
      </div>
    </footer>
  );
}
