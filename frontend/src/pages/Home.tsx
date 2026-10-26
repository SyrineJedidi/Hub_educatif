import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { useAuth, destination } from "../auth/AuthContext";
import "../styles/front/home.css";
const modules: [string, string, string, string, boolean, string][] = [
  ["socle", "ti-calendar", "Groupes, séances et assiduité", "Vos groupes, le calendrier des séances, les feuilles d’appel et un suivi de présence transparent.", true, "emerald"],
  ["quiz", "ti-help-alt", "Quiz et progression", "Des QCM corrigés automatiquement, plusieurs tentatives et des résultats détaillés.", true, "amber"],
  ["resumes", "ti-book", "Résumés et illustrations", "Des fiches de révision rédigées avec l’IA, relues par l’enseignant, et des cartes mémoire.", true, "sage"],
  ["cours", "ti-folder", "Cours et ressources", "Tous les supports de cours rassemblés au même endroit.", false, "sun"],
  ["assistant", "ti-comments", "Assistant pédagogique", "Un accompagnement pour répondre aux questions du quotidien.", false, "apricot"],
  ["coaching", "ti-target", "Planification et coaching", "Organiser son travail et avancer à son rythme.", false, "emerald"],
];
const roles: [string, string, string, string[]][] = [
  ["ti-user", "Étudiant", "emerald", ["Ses séances et son assiduité", "Les quiz de ses groupes", "Les fiches partagées et les cartes de révision", "Ses propres fiches, avec l’IA"]],
  ["ti-blackboard", "Enseignant", "amber", ["L’appel et l’historique des séances", "La création et la correction des quiz", "Des fiches préparées avec l’IA, relues avant partage", "Le suivi de lecture de ses étudiants"]],
  ["ti-settings", "Administration", "sage", ["Les comptes et les rôles", "Les groupes et les inscriptions", "Toutes les fiches et le pilotage de l’IA", "Un back-office dédié"]],
];
const subjects: [string, string][] = [
  ["ti-pulse", "Biologie"], ["ti-ruler-pencil", "Mathématiques"], ["ti-desktop", "Informatique"],
  ["ti-world", "Géographie"], ["ti-bolt", "Physique"], ["ti-comment-alt", "Langues"],
  ["ti-stats-up", "Économie"], ["ti-light-bulb", "Chimie"], ["ti-book", "Histoire"], ["ti-palette", "Arts"],
];
const figures: [string, number, string][] = [
  ["Espaces dédiés", 3, ""],
  ["Modules pédagogiques", 6, ""],
  ["Contenus IA relus avant partage", 100, " %"],
  ["Membres de l’équipe Nexora", 5, ""],
];
const calm = () => window.matchMedia("(prefers-reduced-motion: reduce)").matches;
/** Reveals [data-reveal] blocks as they enter the viewport. */
function useReveal(root: React.RefObject<HTMLElement | null>) {
  useEffect(() => {
    const items = root.current?.querySelectorAll<HTMLElement>("[data-reveal]") || [];
    if (calm() || !("IntersectionObserver" in window)) {
      items.forEach((el) => el.classList.add("is-in"));
      return;
    }
    const io = new IntersectionObserver(
      (entries) =>
        entries.forEach((e) => {
          if (e.isIntersecting) {
            const el = e.target as HTMLElement;
            el.classList.add("is-in");
            io.unobserve(el);
            // The stagger only applies to the entrance, not to later hover effects.
            setTimeout(() => (el.style.transitionDelay = ""), 900);
          }
        }),
      { threshold: 0.15, rootMargin: "0px 0px -40px 0px" },
    );
    items.forEach((el) => io.observe(el));
    return () => io.disconnect();
  }, [root]);
}
/** Counts from 0 to the target value once the figure is visible. */
function Counter({ to, suffix }: { to: number; suffix: string }) {
  const ref = useRef<HTMLElement>(null);
  const [value, setValue] = useState(to);
  useEffect(() => {
    const el = ref.current;
    if (!el || calm() || !("IntersectionObserver" in window)) return;
    setValue(0);
    const io = new IntersectionObserver(([entry]) => {
      if (!entry.isIntersecting) return;
      io.disconnect();
      const start = performance.now();
      const tick = (now: number) => {
        const t = Math.min(1, (now - start) / 1200);
        setValue(Math.round(to * (1 - Math.pow(1 - t, 3))));
        if (t < 1) requestAnimationFrame(tick);
      };
      requestAnimationFrame(tick);
    });
    io.observe(el);
    return () => io.disconnect();
  }, [to]);
  return (
    <dd ref={ref} aria-label={to + suffix}>
      <span aria-hidden="true">
        {value}
        {suffix}
      </span>
    </dd>
  );
}
/** Public home page of the Hub. */
export default function Home() {
  const { user } = useAuth();
  const start = user ? destination(user) : "/inscription";
  const page = useRef<HTMLDivElement>(null);
  useReveal(page);
  return (
    <div className="hm" ref={page}>
      <section className="hm-hero" aria-labelledby="hm-title">
        <div className="hm-aurora" aria-hidden="true">
          <i />
          <i />
          <i />
          <i />
        </div>
        <div className="container hm-hero-grid">
          <div className="hm-hero-text">
            <p className="hm-pill">
              <span className="hm-pill-dot" aria-hidden="true" /> Nouveau · fiches
              de révision illustrées par l’IA
            </p>
            <h1 id="hm-title">
              Vos cours <em>prennent vie</em>. Votre potentiel aussi.
            </h1>
            <p className="hm-rotator">
              Un seul espace pour{" "}
              <span className="hm-words" aria-hidden="true">
                <span>réviser</span>
                <span>comprendre</span>
                <span>s’entraîner</span>
                <span>progresser</span>
              </span>
              <span className="sr-only">réviser, comprendre, s’entraîner et progresser</span>
            </p>
            <p className="hm-lead">
              Étudiants, enseignants et administration partagent un même espace :
              séances et assiduité, quiz, fiches de révision et intelligence
              artificielle relue par vos enseignants.
            </p>
            <div className="hm-actions">
              <Link className="hm-btn hm-btn-primary" to={start}>
                {user ? "Accéder à mon espace" : "Créer mon compte gratuit"}
                <span className="ti-arrow-right" aria-hidden="true" />
              </Link>
              {!user && (
                <Link className="hm-btn hm-btn-ghost" to="/connexion">
                  Se connecter
                </Link>
              )}
            </div>
            <ul className="hm-trust" aria-label="Nos engagements">
              <li>
                <span className="ti-heart" aria-hidden="true" /> Gratuit pour les étudiants
              </li>
              <li>
                <span className="ti-check-box" aria-hidden="true" /> IA relue par l’enseignant
              </li>
              <li>
                <span className="ti-hand-point-up" aria-hidden="true" /> Accessible au clavier
              </li>
            </ul>
          </div>
          <div className="hm-preview" aria-hidden="true">
            <div className="hm-card hm-sheet">
              <span className="hm-chips">
                <span className="hm-chip sage">Biologie végétale</span>
                <span className="hm-chip amber">
                  <span className="ti-wand" /> IA · relue
                </span>
              </span>
              <strong>La photosynthèse</strong>
              <span className="hm-line" />
              <span className="hm-line short" />
              <ol>
                <li>La lumière devient énergie chimique</li>
                <li>Elle a lieu dans les chloroplastes</li>
                <li>Le cycle de Calvin fixe le CO₂</li>
              </ol>
            </div>
            <div className="hm-card hm-score">
              <span className="hm-score-ring">
                <span>6/6</span>
              </span>
              <span>
                <strong>Quiz réussi</strong>
                <small>Photosynthèse — les bases</small>
              </span>
            </div>
            <div className="hm-card hm-presence">
              <small>Assiduité</small>
              <strong>92 %</strong>
              <span className="hm-bars">
                <i style={{ height: "60%" }} />
                <i style={{ height: "85%" }} />
                <i style={{ height: "70%" }} />
                <i style={{ height: "95%" }} />
                <i style={{ height: "88%" }} />
              </span>
            </div>
            <span className="hm-spark s1" />
            <span className="hm-spark s2" />
            <span className="hm-spark s3" />
          </div>
        </div>
      </section>
      <section className="hm-marquee" aria-label="Toutes les matières">
        <div className="hm-marquee-track">
          {[0, 1].map((copy) => (
            <ul key={copy} aria-hidden={copy === 1}>
              {subjects.map(([icon, label]) => (
                <li key={label}>
                  <span className={icon} aria-hidden="true" /> {label}
                </li>
              ))}
            </ul>
          ))}
        </div>
      </section>
      <section className="hm-figures" aria-label="Le Hub en chiffres">
        <div className="container">
          <dl data-reveal>
            {figures.map(([label, value, suffix]) => (
              <div key={label}>
                <dt>{label}</dt>
                <Counter to={value} suffix={suffix} />
              </div>
            ))}
          </dl>
        </div>
      </section>
      <section id="modules" className="hm-section" aria-labelledby="hm-modules">
        <div className="container">
          <header className="hm-head" data-reveal>
            <p className="hm-eyebrow">Les modules</p>
            <h2 id="hm-modules">
              Une plateforme qui <em>grandit</em> avec vous
            </h2>
            <p>
              Le socle commun est disponible ; les modules suivants arrivent
              progressivement, développés chacun par un membre de l’équipe.
            </p>
          </header>
          <ul className="hm-modules">
            {modules.map(([slug, icon, title, text, ready, tone], index) => (
              <li
                key={slug}
                className={"tone-" + tone + (ready ? "" : " is-soon")}
                data-reveal
                style={{ transitionDelay: (index % 3) * 90 + "ms" }}
              >
                <span className={"hm-module-icon " + icon} aria-hidden="true" />
                <h3>{title}</h3>
                <p>{text}</p>
                <span className={"hm-status" + (ready ? " ready" : "")}>
                  {ready ? "Disponible" : "En préparation"}
                </span>
                {slug !== "socle" && (
                  <Link className="hm-module-link" to={"/modules/" + slug} aria-label={"Découvrir le module " + title}>
                    Découvrir <span className="ti-arrow-right" aria-hidden="true" />
                  </Link>
                )}
              </li>
            ))}
          </ul>
        </div>
      </section>
      <section id="parcours" className="hm-section hm-alt" aria-labelledby="hm-roles">
        <div className="container">
          <header className="hm-head" data-reveal>
            <p className="hm-eyebrow">Notre approche</p>
            <h2 id="hm-roles">
              À chacun son espace, <em>tous le même élan</em>
            </h2>
            <p>
              Chaque rôle dispose de ses outils dans un environnement commun : les
              droits sont vérifiés par le serveur à chaque action.
            </p>
          </header>
          <ul className="hm-roles">
            {roles.map(([icon, title, tone, items], index) => (
              <li key={title} className={"tone-" + tone} data-reveal style={{ transitionDelay: index * 90 + "ms" }}>
                <span className={"hm-role-icon " + icon} aria-hidden="true" />
                <h3>{title}</h3>
                <ul>
                  {items.map((item) => (
                    <li key={item}>
                      <span className="ti-check" aria-hidden="true" /> {item}
                    </li>
                  ))}
                </ul>
              </li>
            ))}
          </ul>
        </div>
      </section>
      <section className="hm-section" aria-labelledby="hm-ai">
        <div className="container hm-ai">
          <div data-reveal>
            <p className="hm-eyebrow amber">Intelligence artificielle</p>
            <h2 id="hm-ai">
              L’IA prépare, <em>l’enseignant valide</em>
            </h2>
            <p>
              Un chapitre ou un PDF devient une fiche de révision : résumé structuré,
              points clés, glossaire et illustration. Rien n’est partagé avec les
              étudiants avant la relecture de l’enseignant.
            </p>
            <ol className="hm-steps">
              <li>
                <strong>Le cours</strong> est importé, la génération continue en
                arrière-plan.
              </li>
              <li>
                <strong>L’IA rédige</strong> avec Gemini, et un modèle local prend
                le relais si besoin.
              </li>
              <li>
                <strong>L’enseignant relit</strong>, note la pertinence puis publie
                pour son groupe.
              </li>
            </ol>
          </div>
          <div className="hm-card hm-quality" aria-hidden="true" data-reveal>
            <p className="hm-quality-title">
              <span className="ti-pulse" /> Qualité mesurée de chaque résumé
            </p>
            <p className="hm-typing">
              <span className="ti-wand" /> Génération de la fiche « Photosynthèse »
              <i />
              <i />
              <i />
            </p>
            {[
              ["Mots-clés du cours couverts", 86],
              ["Structure respectée", 100],
              ["Relu par l’enseignant", 100],
            ].map(([label, value]) => (
              <div className="hm-meter" key={label}>
                <span>{label}</span>
                <span className="hm-meter-track">
                  <i style={{ width: value + "%" }} />
                </span>
                <strong>{value} %</strong>
              </div>
            ))}
          </div>
        </div>
      </section>
      <section className="hm-section hm-alt" aria-labelledby="hm-start">
        <div className="container">
          <header className="hm-head" data-reveal>
            <p className="hm-eyebrow">Premiers pas</p>
            <h2 id="hm-start">
              Commencer en <em>trois étapes</em>
            </h2>
          </header>
          <ol className="hm-start" data-reveal>
            <li>
              <span className="hm-start-num">1</span>
              <h3>Créez votre compte</h3>
              <p>Étudiant ou enseignant, en quelques secondes.</p>
            </li>
            <li>
              <span className="hm-start-num">2</span>
              <h3>Rejoignez vos groupes</h3>
              <p>L’administration vous inscrit dans vos groupes pédagogiques.</p>
            </li>
            <li>
              <span className="hm-start-num">3</span>
              <h3>Apprenez et progressez</h3>
              <p>Séances, quiz et fiches de révision vous attendent dans votre espace.</p>
            </li>
          </ol>
        </div>
      </section>
      <section id="nexora" className="hm-section" aria-labelledby="hm-team">
        <div className="container">
          <div className="hm-cta" data-reveal>
            <span className="hm-cta-bubble b1" aria-hidden="true" />
            <span className="hm-cta-bubble b2" aria-hidden="true" />
            <div>
              <p className="hm-eyebrow light">L’équipe Nexora</p>
              <h2 id="hm-team">Un projet académique, cinq membres, une ambition</h2>
              <p>
                Rapprocher apprentissage et accompagnement, dans un espace clair,
                sûr et accessible à tous.
              </p>
            </div>
            <Link className="hm-btn hm-btn-light" to={start}>
              {user ? "Retourner à mon espace" : "Commencer mon parcours"}
              <span className="ti-arrow-right" aria-hidden="true" />
            </Link>
          </div>
        </div>
      </section>
    </div>
  );
}
