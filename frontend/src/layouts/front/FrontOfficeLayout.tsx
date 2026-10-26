import { Suspense } from "react";
import { useEffect, useRef, useState } from "react";
import { Link, NavLink, Outlet, useLocation } from "react-router-dom";
import { useAuth, destination } from "../../auth/AuthContext";
import { Alert, Loading, statuses } from "../../components/UI";
import "../../styles/front/front-office.css";
import "../../styles/front/portal.css";
import "../../styles/front/front-theme.css";
import "../../styles/front/aurora.css";
import { useTemplate } from "../template";
export function Brand() {
  return (
    <Link
      className="brand"
      to="/"
      aria-label="Hub Éducatif Multimodal — accueil"
    >
      <span className="brand-mark" aria-hidden="true">
        <span className="ti-book" />
      </span>
      <span>
        Hub Éducatif Multimodal<small>Apprendre, réviser, progresser</small>
      </span>
    </Link>
  );
}
const modules = [
  ["cours", "Cours et ressources", "En préparation"],
  ["resumes", "Résumés et illustrations", "Fiches, résumés IA et illustrations"],
  ["assistant", "Assistant pédagogique", "Réponses sourcées, par texte ou par voix"],
  ["quiz", "Quiz et progression", "Quiz, tentatives et correction"],
  ["coaching", "Planification et coaching", "En préparation"],
];
export default function FrontOfficeLayout() {
  useTemplate("front");
  const { user, logout } = useAuth();
  const { pathname } = useLocation();
  const [open, setOpen] = useState(false),
    [error, setError] = useState<unknown>();
  const header = useRef<HTMLElement>(null),
    toggle = useRef<HTMLButtonElement>(null),
    nav = useRef<HTMLElement>(null);
  const base = user?.role === "ADMIN" ? "/administration" : "/espace";
  const backOffice =
    user?.role === "ADMIN"
      ? "/administration"
      : user?.role === "TEACHER"
        ? "/gestion"
        : "";
  const spaceLabel =
    user?.role === "TEACHER"
      ? "Espace enseignant"
      : user?.role === "ADMIN"
        ? "Tableau de bord"
        : "Mon espace";
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
        Aller au contenu
      </a>
      <header
        ref={header}
        id="navigation"
        className={"portal-header" + (user ? " is-connected" : "")}
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
        <div className="portal-utility">
          <div className="container">
            <p>
              <span className="ti-world" aria-hidden="true" /> Plateforme
              pédagogique · Équipe Nexora — ESPRIT
            </p>
            <p className="portal-utility-right">
              Année universitaire 2026 – 2027
              {user && <span className="portal-role">{statuses[user.role]}</span>}
            </p>
          </div>
        </div>
        <div className="container portal-bar">
          <Brand />
          <div className="portal-bar-actions">
            {user ? (
              <>
                {backOffice && (
                  <Link className="portal-backoffice" to={backOffice}>
                    <span className="ti-settings" aria-hidden="true" />{" "}
                    Back-office
                  </Link>
                )}
                <details className="profile-menu front-profile">
                  <summary
                    aria-label={
                      "Menu de profil de " + user.first_name + " " + user.last_name
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
                      <small>{statuses[user.role]}</small>
                    </span>
                    <span aria-hidden="true" className="ti-angle-down" />
                  </summary>
                  <div>
                    <Link
                      to={base + "/profil"}
                      onClick={() => {
                        setOpen(false);
                        closeMenus();
                      }}
                    >
                      Mon profil
                    </Link>
                    <button onClick={() => void logout().catch(setError)}>
                      Se déconnecter
                    </button>
                  </div>
                </details>
              </>
            ) : (
              <>
                <Link className="portal-login" to="/connexion">
                  <span className="ti-user" aria-hidden="true" /> Connexion
                </Link>
                <Link className="portal-signup" to="/inscription">
                  Créer un compte
                </Link>
              </>
            )}
            <button
              ref={toggle}
              className="mobile-toggle"
              aria-expanded={open}
              aria-controls="public-nav"
              onClick={toggleNavigation}
            >
              <span className="ti-menu" aria-hidden="true" /> Menu
            </button>
          </div>
        </div>
        <nav
          ref={nav}
          id="public-nav"
          className={"portal-nav" + (open ? " open" : "")}
          aria-label="Navigation principale"
          onClick={(e) => {
            if ((e.target as HTMLElement).closest("a")) {
              setOpen(false);
              closeMenus();
            }
          }}
        >
          <div className="container">
            <NavLink to="/" end>
              Accueil
            </NavLink>
            {user ? (
              <>
                <NavLink to={destination(user)} end>
                  {spaceLabel}
                </NavLink>
                {user.role === "ADMIN" ? (
                  <>
                    <NavLink to="/administration/resumes">
                      Résumés et illustrations
                    </NavLink>
                    <NavLink to="/administration/quiz">Quiz</NavLink>
                    <NavLink to="/administration/assistant">Assistant</NavLink>
                    <NavLink to="/administration/seances">Séances</NavLink>
                    <NavLink to="/administration/utilisateurs">
                      Utilisateurs
                    </NavLink>
                  </>
                ) : (
                  <>
                    <NavLink to="/espace/fiches">Fiches de révision</NavLink>
                    <NavLink to="/espace/quiz">Quiz</NavLink>
                    <NavLink to="/espace/assistant">Assistant</NavLink>
                    <NavLink to="/espace/seances">
                      {user.role === "TEACHER" ? "Séances et appel" : "Mes séances"}
                    </NavLink>
                    <NavLink to="/espace/assiduite">Assiduité</NavLink>
                    <NavLink to="/espace/groupes">Groupes</NavLink>
                  </>
                )}
                <details className="front-dropdown">
                  <summary>
                    Tous les modules{" "}
                    <span aria-hidden="true" className="ti-angle-down" />
                  </summary>
                  <div>
                    {modules.map(([slug, label, help]) => (
                      <Link key={slug} to={"/modules/" + slug}>
                        {label}
                        <small>{help}</small>
                      </Link>
                    ))}
                  </div>
                </details>
              </>
            ) : (
              <>
                <a href="/#parcours">Notre approche</a>
                <a href="/#modules">Les modules</a>
                <a href="/#nexora">L’équipe Nexora</a>
              </>
            )}
          </div>
        </nav>
      </header>
      {!!error && (
        <div className="container">
          <Alert error={error} />
        </div>
      )}
      <main id="main" tabIndex={-1}>
        <Suspense fallback={<Loading />}>
            <Outlet />
          </Suspense>
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
    <footer className="portal-footer">
      <div className="footer section-padding">
        <div className="container">
          <div className="row">
            <div className="col-lg-3 col-sm-6">
              <div className="single_footer">
                <Brand />
                <p>
                  Vos cours prennent vie. Votre potentiel aussi. Un projet
                  académique porté par l’équipe Nexora.
                </p>
              </div>
            </div>
            <div className="col-lg-2 col-sm-6">
              <div className="single_footer">
                <h2>Votre espace</h2>
                <ul>
                  <li>
                    <Link to={user ? destination(user) : "/connexion"}>
                      {user ? "Mon espace" : "Se connecter"}
                    </Link>
                  </li>
                  <li>
                    <Link to={user ? base + "/profil" : "/inscription"}>
                      {user ? "Mon profil" : "Créer un compte"}
                    </Link>
                  </li>
                  <li>
                    <Link to="/mot-de-passe-oublie">Mot de passe oublié</Link>
                  </li>
                </ul>
              </div>
            </div>
            <div className="col-lg-2 col-sm-6">
              <div className="single_footer">
                <h2>Au quotidien</h2>
                <ul>
                  <li>
                    <Link to={user ? learning + "/groupes" : learning}>
                      Mes groupes
                    </Link>
                  </li>
                  <li>
                    <Link to={user ? learning + "/seances" : learning}>
                      Mes séances
                    </Link>
                  </li>
                  <li>
                    <Link to={user ? learning + "/assiduite" : learning}>
                      Mon assiduité
                    </Link>
                  </li>
                </ul>
              </div>
            </div>
            <div className="col-lg-3 col-sm-6">
              <div className="single_footer">
                <h2>Apprendre autrement</h2>
                <ul>
                  <li>
                    <Link to="/modules/cours">Cours et ressources</Link>
                  </li>
                  <li>
                    <Link to="/modules/resumes">Résumés et illustrations</Link>
                  </li>
                  <li>
                    <Link to="/modules/assistant">Assistant pédagogique</Link>
                  </li>
                  <li>
                    <Link to="/modules/quiz">Quiz et progression</Link>
                  </li>
                </ul>
              </div>
            </div>
            <div className="col-lg-2 col-sm-6">
              <div className="single_footer">
                <h2>Nexora</h2>
                <p>
                  Cinq membres, une ambition : rapprocher apprentissage et
                  accompagnement.
                </p>
              </div>
            </div>
          </div>
        </div>
      </div>
      <div className="foot_copy">
        <div className="footer_copyright">
          <p>
            Hub Éducatif Multimodal · Équipe Nexora — ESPRIT
            <br />
            Template © 2024 <a href="https://bestwpware.com/">Bestwpware</a> ·
            Distribution <a href="https://themewagon.com/">ThemeWagon</a>
          </p>
        </div>
      </div>
    </footer>
  );
}
