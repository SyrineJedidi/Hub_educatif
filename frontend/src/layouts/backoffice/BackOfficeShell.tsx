import { Suspense } from "react";
import { Link, NavLink, Outlet, useLocation } from "react-router-dom";
import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { useAuth } from "../../auth/AuthContext";
import { Alert, Loading, statuses } from "../../components/UI";
import { useTemplate } from "../template";
import { LanguageSelect, t } from "../../quizzes/i18n";
import "../../styles/backoffice/backoffice.css";
export interface BackOfficeLink {
  to: string;
  icon: string;
  label: string;
  end?: boolean;
  soon?: boolean;
}
export interface BackOfficeSection {
  title: string;
  links: BackOfficeLink[];
}
/**
 * Back-office template (Soft UI Dashboard by Creative Tim, MIT), separate from the
 * public site (Eduleb): used by the administration and by the teacher management area.
 */
export default function BackOfficeShell({
  area,
  sections,
  siteLink,
}: {
  area: string;
  sections: BackOfficeSection[];
  siteLink: string;
}) {
  useTemplate("back");
  const { user, logout } = useAuth(),
    { pathname } = useLocation();
  const [open, setOpen] = useState(false),
    [menu, setMenu] = useState(false),
    [logoutError, setLogoutError] = useState<unknown>();
  const menuRef = useRef<HTMLLIElement>(null),
    toggleRef = useRef<HTMLButtonElement>(null);
  // Soft UI drives its layout from classes on <body>.
  useLayoutEffect(() => {
    document.body.classList.add("g-sidenav-show", "bg-gray-100");
    return () => document.body.classList.remove("g-sidenav-show", "bg-gray-100", "g-sidenav-pinned");
  }, []);
  useEffect(() => {
    document.body.classList.toggle("g-sidenav-pinned", open);
  }, [open]);
  useEffect(() => {
    setOpen(false);
    setMenu(false);
  }, [pathname]);
  useEffect(() => {
    const outside = (e: PointerEvent) => {
      if (!menuRef.current?.contains(e.target as Node)) setMenu(false);
    };
    document.addEventListener("pointerdown", outside);
    return () => document.removeEventListener("pointerdown", outside);
  }, []);
  if (!user) return null;
  // The most specific link matching the address names the current page.
  const current = sections
    .flatMap((s) => s.links.map((l) => ({ ...l, section: s.title })))
    .filter((l) =>
      l.end ? pathname === l.to : pathname === l.to || pathname.startsWith(l.to + "/"),
    )
    .sort((a, b) => b.to.length - a.to.length)[0];
  const initials = user.first_name.charAt(0) + user.last_name.charAt(0);
  const profile = (user.role === "ADMIN" ? "/administration" : "/espace") + "/profil";
  return (
    <div className="bo">
      <a className="skip-link" href="#main">
        Aller au contenu
      </a>
      <aside
        className="sidenav navbar navbar-vertical navbar-expand-xs border-0 border-radius-xl my-3 fixed-start ms-3 bg-white bo-sidenav"
        id="sidenav-main"
        aria-label="Menu du back-office"
        onKeyDown={(e) => {
          if (e.key === "Escape" && open) {
            setOpen(false);
            toggleRef.current?.focus();
          }
        }}
      >
        <div className="sidenav-header">
          <Link className="navbar-brand m-0 d-flex align-items-center" to={siteLink}>
            <span className="bo-brand-mark" aria-hidden="true">
              <span className="ti-book" />
            </span>
            <span className="ms-2 bo-brand-text">
              <span className="font-weight-bold">Hub Éducatif</span>
              <small>Back-office · {area}</small>
            </span>
          </Link>
        </div>
        <hr className="horizontal dark mt-0" />
        <div className="collapse navbar-collapse w-auto h-auto show" id="sidenav-collapse-main">
          <ul className="navbar-nav">
            {sections.map((section) => (
              <li className="nav-item bo-group" key={section.title}>
                <h6 className="ps-4 ms-2 text-uppercase text-xs font-weight-bolder bo-group-title" id={"bo-" + section.title}>
                  {t(section.title)}
                </h6>
                <ul className="navbar-nav" aria-labelledby={"bo-" + section.title}>
                  {section.links.map((link) => {
                    const active = current?.to === link.to;
                    return (
                      <li className="nav-item" key={link.to}>
                        <NavLink
                          className={"nav-link" + (active ? " active" : "")}
                          to={link.to}
                          end={link.end}
                          aria-current={active ? "page" : undefined}
                        >
                          <span className="icon icon-shape icon-sm shadow border-radius-md bg-white text-center me-2 d-flex align-items-center justify-content-center" aria-hidden="true">
                            <span className={link.icon} />
                          </span>
                          <span className="nav-link-text ms-1">{t(link.label)}</span>
                          {link.soon && <span className="badge badge-sm bg-gradient-secondary ms-auto">Bientôt</span>}
                        </NavLink>
                      </li>
                    );
                  })}
                </ul>
              </li>
            ))}
          </ul>
        </div>
        <div className="sidenav-footer mx-3 mt-3 mb-4">
          <div className="card card-background shadow-none card-background-mask-secondary bo-help">
            <div className="full-background" style={{ backgroundImage: "url('/assets/backoffice/img/white-curved.jpg')" }} />
            <div className="card-body text-start p-3 w-100">
              <div className="icon icon-shape icon-sm bg-white shadow text-center mb-3 d-flex align-items-center justify-content-center border-radius-md" aria-hidden="true">
                <span className="ti-world text-dark" />
              </div>
              <h6 className="text-white up mb-0">Espace public</h6>
              <p className="text-xs font-weight-bold text-white">Voir le site tel que le voient les étudiants.</p>
              <Link className="btn btn-white btn-sm w-100 mb-0" to={siteLink}>
                Retour au site
              </Link>
            </div>
          </div>
        </div>
      </aside>
      {open && <button type="button" className="bo-backdrop" aria-label="Fermer le menu" onClick={() => setOpen(false)} />}
      <main id="main" className="main-content position-relative max-height-vh-100 h-100 border-radius-lg" tabIndex={-1}>
        <nav className="navbar navbar-main navbar-expand-lg px-0 mx-4 shadow-none border-radius-xl bo-navbar" aria-label="Barre supérieure">
          <div className="container-fluid py-1 px-3">
            <nav aria-label="Fil d’Ariane">
              <ol className="breadcrumb bg-transparent mb-0 pb-0 pt-1 px-0 me-sm-6 me-5">
                <li className="breadcrumb-item text-sm">
                  <span className="opacity-7 text-dark">Back-office {area}</span>
                </li>
                <li className="breadcrumb-item text-sm text-dark active" aria-current="page">
                  {t(current?.section || area)}
                </li>
              </ol>
              <p className="font-weight-bolder mb-0 bo-page-name">{t(current?.label || area)}</p>
            </nav>
            <ul className="navbar-nav ms-auto flex-row align-items-center justify-content-end gap-3">
              <li className="nav-item d-flex align-items-center">
                <LanguageSelect />
              </li>
              <li className="nav-item d-none d-md-flex align-items-center">
                <Link className="btn btn-outline-primary btn-sm mb-0" to={siteLink}>
                  <span className="ti-new-window me-1" aria-hidden="true" /> Voir le site
                </Link>
              </li>
              <li className="nav-item d-none d-sm-flex align-items-center">
                <span className={"badge badge-sm " + (user.role === "ADMIN" ? "bg-gradient-dark" : "bg-gradient-success")}>
                  {statuses[user.role]}
                </span>
              </li>
              <li className="nav-item dropdown d-flex align-items-center" ref={menuRef}>
                <button
                  type="button"
                  className="nav-link text-body p-0 d-flex align-items-center bo-user"
                  aria-expanded={menu}
                  aria-haspopup="true"
                  aria-label={"Menu de " + user.first_name + " " + user.last_name}
                  onClick={() => setMenu(!menu)}
                >
                  <span className="avatar avatar-sm bg-gradient-primary me-2">
                    {user.avatar ? <img src={user.avatar} alt="" /> : initials}
                  </span>
                  <span className="d-none d-lg-inline text-sm font-weight-bold">
                    {user.first_name} {user.last_name}
                  </span>
                  <span className="ti-angle-down ms-2 text-xs" aria-hidden="true" />
                </button>
                <ul className={"dropdown-menu dropdown-menu-end px-2 py-3 me-sm-n4" + (menu ? " show" : "")}>
                  <li>
                    <Link className="dropdown-item border-radius-md" to={profile}>
                      <span className="ti-id-badge me-2" aria-hidden="true" /> Mon profil
                    </Link>
                  </li>
                  <li>
                    <Link className="dropdown-item border-radius-md" to={siteLink}>
                      <span className="ti-world me-2" aria-hidden="true" /> Site public
                    </Link>
                  </li>
                  <li>
                    <button
                      type="button"
                      className="dropdown-item border-radius-md text-danger"
                      onClick={() => void logout().catch(setLogoutError)}
                    >
                      <span className="ti-power-off me-2" aria-hidden="true" /> Se déconnecter
                    </button>
                  </li>
                </ul>
              </li>
              <li className="nav-item d-xl-none d-flex align-items-center">
                <button
                  ref={toggleRef}
                  type="button"
                  className="btn btn-sm btn-outline-dark mb-0 bo-toggler"
                  aria-controls="sidenav-main"
                  aria-expanded={open}
                  aria-label={open ? "Fermer le menu" : "Ouvrir le menu"}
                  onClick={() => setOpen(!open)}
                >
                  <span className={open ? "ti-close" : "ti-menu"} aria-hidden="true" />
                  <span className="ms-1">Menu</span>
                </button>
              </li>
            </ul>
          </div>
        </nav>
        <div className="container-fluid py-4" key={pathname}>
          <Alert error={logoutError} />
          <Suspense fallback={<Loading />}>
            <Outlet />
          </Suspense>
          <footer className="footer pt-5">
            <p className="text-sm mb-0 bo-footer-text">
              Hub Éducatif Multimodal · Back-office {area} · Équipe Nexora — ESPRIT ·
              Template Soft UI Dashboard par Creative Tim (MIT)
            </p>
          </footer>
        </div>
      </main>
    </div>
  );
}
