import {
  Categories,
  Roles,
  Benefits,
  GettingStarted,
} from "../components/HomeSections";
import { Link } from "react-router-dom";
const modules = [
  [
    "cours",
    "Cours et ressources",
    "Retrouvez vos supports dans un même espace.",
  ],
  [
    "resumes",
    "Résumés et illustrations",
    "Explorez de nouvelles façons de comprendre.",
  ],
  [
    "assistant",
    "Assistant pédagogique",
    "Un accompagnement pour vos apprentissages.",
  ],
  [
    "quiz",
    "Quiz et progression",
    "Évaluez vos acquis et suivez votre évolution.",
  ],
  [
    "coaching",
    "Planification et coaching",
    "Organisez votre travail, à votre rythme.",
  ],
];
export default function Home() {
  return (
    <>
      <section
        className="home_bg hb_height"
        style={{
          backgroundImage: "url(/assets/img/bg/home-bg.jpg)",
          backgroundSize: "cover",
          backgroundPosition: "center",
        }}
      >
        <div className="container">
          <div className="row">
            <div className="col-lg-6 col-sm-12">
              <div className="hero-text ht_top">
                <h1>
                  <span>Vos cours prennent vie.</span> Votre potentiel aussi.
                </h1>
                <p>
                  Étudiants et enseignants, partagez un même espace pour vos
                  groupes, vos séances et le suivi de votre assiduité.
                </p>
              </div>
              <div className="home_sb">
                <div className="banner_subs hero-action">
                  <span>Votre parcours commence ici</span>
                  <Link to="/inscription" className="subscribe__btn">
                    Rejoindre <span aria-hidden="true">↗</span>
                  </Link>
                </div>
              </div>
            </div>
            <div className="col-lg-6 col-sm-12">
              <div className="hero-text-img">
                <img
                  src="/assets/img/home-img2.png"
                  className="img-fluid"
                  alt="Étudiante avec ses supports de cours"
                />
                <div className="home_ps">
                  <span className="ti-user" aria-hidden="true" />
                  <h2>Nexora</h2>
                  <p>Notre collectif</p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>
      <section
        className="count_area counter_feature"
        aria-label="Les bénéfices du Hub"
      >
        <div className="container">
          <div className="row">
            {[
              ["ti-folder", "Groupes", "Un collectif pour apprendre"],
              ["ti-calendar", "Séances", "Un calendrier partagé"],
              ["ti-id-badge", "Présences", "Un suivi transparent"],
              ["ti-user", "Profils", "Un espace pour chacun"],
            ].map(([icon, title, text], i) => (
              <div className="col-lg-3 col-sm-6" key={title}>
                <div className="single-counter">
                  <span
                    className={
                      icon + " sc_" + ["one", "two", "three", "four"][i]
                    }
                    aria-hidden="true"
                  />
                  <h2>{title}</h2>
                  <p>{text}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>
      <section
        id="parcours"
        className="top_cat__area section-padding"
        style={{
          backgroundImage: "url(/assets/img/bg/shape-1.png)",
          backgroundSize: "cover",
          backgroundPosition: "center",
        }}
      >
        <div className="container">
          <div className="section-title text-center">
            <h2>Ensemble, donnons du sens à votre parcours</h2>
            <p>
              Un point de rencontre entre étudiants, enseignants et
              administration. Les outils essentiels pour mieux organiser la vie
              pédagogique.
            </p>
          </div>
          <div className="row">
            {[
              [
                "Vos",
                "groupes",
                "Retrouvez vos groupes pédagogiques et votre enseignant responsable.",
              ],
              [
                "Vos",
                "séances",
                "Consultez les rendez-vous, les horaires et les lieux de vos séances.",
              ],
              [
                "Votre",
                "assiduité",
                "Suivez vos présences, retards et absences en toute transparence.",
              ],
              [
                "Votre",
                "profil",
                "Gardez un espace personnel simple, clair et à votre image.",
              ],
            ].map(([a, b, c], i) => (
              <div className="col-lg-3 col-sm-6" key={b}>
                <div className="single_tp">
                  <span className={"sc_" + ["one", "two", "three", "four"][i]}>
                    0{i + 1}
                  </span>
                  <h3>
                    {a}
                    <br />
                    {b}
                  </h3>
                  <p>{c}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>
      <section id="nexora" className="ab_area section-padding">
        <div className="container">
          <div className="row">
            <div className="col-lg-6">
              <div className="ab_img">
                <img
                  src="/assets/img/about1.png"
                  className="img-fluid"
                  alt="Une étudiante poursuit son apprentissage"
                />
              </div>
            </div>
            <div className="col-lg-6">
              <div className="ab_content">
                <h2>Un même espace pour apprendre et avancer ensemble</h2>
                <p>
                  Le Hub Éducatif Multimodal est un projet académique de
                  l’équipe Nexora, composée de cinq membres. Il rassemble les
                  essentiels de votre quotidien pédagogique.
                </p>
                <p>
                  Chaque rôle dispose de ses propres outils, dans un
                  environnement commun : l’étudiant suit son parcours,
                  l’enseignant accompagne ses groupes et l’administration
                  organise les affectations.
                </p>
                <ul>
                  {[
                    "Des groupes et des inscriptions avec un historique préservé",
                    "Des séances organisées et des feuilles d’appel partagées",
                    "Un suivi de l’assiduité accessible et compréhensible",
                  ].map((t) => (
                    <li key={t}>
                      <span className="ti-check" aria-hidden="true" /> {t}
                    </li>
                  ))}
                </ul>
                <Link className="btn_one" to="/inscription">
                  Commencer mon parcours ↗
                </Link>
              </div>
            </div>
          </div>
        </div>
      </section>
      <Categories />
      <section id="modules" className="home_course section-padding">
        <div className="container">
          <div className="section-title text-center">
            <h2>Une plateforme qui grandit avec vous</h2>
            <p>
              Groupes, séances et assiduité constituent notre socle commun. Les
              modules suivants sont en préparation et seront développés
              progressivement.
            </p>
          </div>
          <div className="row">
            <div className="col-lg-4 col-md-6">
              <article className="single_course">
                <div className="single_c_img">
                  <img
                    src="/assets/img/course/6.png"
                    alt=""
                    className="img-fluid"
                  />
                  <span>Socle commun</span>
                </div>
                <h3 className="module-title">
                  <Link to="/connexion">Groupes, séances et assiduité</Link>
                </h3>
                <p>Les essentiels pour organiser la vie pédagogique.</p>
                <div className="course_meta">
                  <Link to="/connexion">Accéder à mon espace ↗</Link>
                </div>
              </article>
            </div>
            {modules.map(([slug, title, text], i) => (
              <div className="col-lg-4 col-md-6" key={slug}>
                <article className="single_course">
                  <div className="single_c_img">
                    <img
                      className="img-fluid"
                      src={"/assets/img/course/" + (i + 1) + ".png"}
                      alt=""
                    />
                    <span>En préparation</span>
                  </div>
                  <h3 className="module-title">
                    <Link to={"/modules/" + slug}>{title}</Link>
                  </h3>
                  <p>{text}</p>
                  <div className="course_meta">
                    <Link to={"/modules/" + slug}>Découvrir le module ↗</Link>
                  </div>
                </article>
              </div>
            ))}
          </div>
        </div>
      </section>
      <Roles />
      <section className="ab_area section-padding">
        <div className="container">
          <div className="row align-items-center">
            <div className="col-lg-6">
              <div className="ab_content">
                <h2>Votre prochain chapitre commence avec Nexora</h2>
                <p>
                  Créez votre compte étudiant ou enseignant et retrouvez votre
                  espace personnel. Votre administration vous inscrira ensuite
                  dans vos groupes pédagogiques.
                </p>
                <Link to="/inscription" className="btn_one">
                  Créer mon compte ↗
                </Link>
              </div>
            </div>
            <div className="col-lg-6">
              <img
                className="img-fluid"
                src="/assets/img/about3.png"
                alt=""
                onError={(e) => {
                  e.currentTarget.style.display = "none";
                }}
              />
            </div>
          </div>
        </div>
      </section>
      <Benefits />
      <GettingStarted />
    </>
  );
}
