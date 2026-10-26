import { useState } from "react";
import { Link } from "react-router-dom";
export function Categories() {
  return (
    <section
      className="top_cat__area section-padding"
      style={{
        backgroundImage: "url(/assets/img/bg/section-2.jpg)",
        backgroundSize: "cover",
        backgroundPosition: "center",
      }}
    >
      <div className="container">
        <div className="section-title text-center">
          <h2>Les essentiels de votre quotidien</h2>
          <p>
            Retrouvez les outils du socle pédagogique et découvrez les prochains
            modules du Hub.
          </p>
        </div>
        <div className="cat_list">
          <ul>
            {[
              ["Mes groupes", "/connexion"],
              ["Mes séances", "/connexion"],
              ["Mon assiduité", "/connexion"],
              ["Cours et ressources", "/modules/cours"],
              ["Assistant pédagogique", "/modules/assistant"],
              ["Quiz et progression", "/modules/quiz"],
            ].map(([label, path], i) => (
              <li key={label}>
                <Link to={path}>
                  <img src={"/assets/img/e" + (i + 1) + ".png"} alt="" />
                  {label}
                </Link>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </section>
  );
}
export function Roles() {
  return (
    <>
      <div className="partner-logo section-padding">
        <div className="container">
          <div className="row part_bg">
            <div className="col-lg-4">
              <div className="partner_title">
                <h2>
                  Un socle commun,
                  <br />
                  <span>des parcours adaptés</span>
                </h2>
              </div>
            </div>
            <div className="col-lg-8">
              <div className="hub-benefits">
                {[
                  "Comptes et profils",
                  "Groupes pédagogiques",
                  "Séances partagées",
                  "Suivi de l’assiduité",
                ].map((label, i) => (
                  <div key={label}>
                    <span
                      className={
                        [
                          "ti-id-badge",
                          "ti-folder",
                          "ti-calendar",
                          "ti-bar-chart",
                        ][i]
                      }
                      aria-hidden="true"
                    />
                    <p>{label}</p>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      </div>
      <section className="vid_area section-padding">
        <div className="container">
          <div
            className="video-area hub-photo-banner"
            style={{
              backgroundImage: "url(/assets/img/bg/video.jpg)",
              backgroundSize: "cover",
              backgroundPosition: "center",
            }}
          >
            <div>
              <p className="eyebrow">APPRENDRE NOUS RASSEMBLE</p>
              <h2>
                Un lieu commun.
                <br />
                Des possibilités à partager.
              </h2>
              <Link to="/connexion" className="btn_one">
                Découvrir mon espace ↗
              </Link>
            </div>
          </div>
        </div>
      </section>
      <section className="team_area section-padding">
        <div className="container">
          <div className="section-title text-center">
            <h2>À chacun son espace, à tous le même élan</h2>
            <p>
              Les outils s’adaptent à votre rôle. Les photographies illustrent
              les usages du Hub et ne présentent pas les membres de Nexora.
            </p>
          </div>
          <div className="row justify-content-center">
            {[
              [
                "Étudiant",
                "Suivre son parcours",
                "Groupes, séances et assiduité",
              ],
              [
                "Enseignant",
                "Accompagner ses groupes",
                "Séances, appel et statistiques",
              ],
              [
                "Administrateur",
                "Organiser la vie pédagogique",
                "Comptes, groupes et affectations",
              ],
            ].map(([role, title, text], i) => (
              <div className="col-lg-3 col-sm-6" key={role}>
                <div className="our-team">
                  <div className="team-content">
                    <img
                      src={"/assets/img/team/team" + (i + 1) + ".jpg"}
                      alt=""
                    />
                  </div>
                  <div className="team-prof">
                    <h3>{role}</h3>
                    <span>{title}</span>
                  </div>
                  <div className="sth_det2">
                    <p>{text}</p>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>
    </>
  );
}
const benefits = [
  [
    "Un suivi transparent",
    "Les statuts non renseignés restent distincts des absences. Seules les feuilles validées des séances passées entrent dans le calcul de l’assiduité.",
    "Comprendre son assiduité",
  ],
  [
    "Un historique préservé",
    "Les périodes d’inscription et les participants des feuilles d’appel sont conservés. Chaque correction après validation exige un motif.",
    "Garder une trace fiable",
  ],
  [
    "Un accès adapté",
    "Étudiants, enseignants et administrateurs disposent d’outils adaptés à leur rôle. Chaque étudiant consulte ses propres données d’assiduité.",
    "Partager le bon espace",
  ],
];
export function Benefits() {
  const [current, setCurrent] = useState(0),
    [title, text, label] = benefits[current];
  return (
    <section className="testi_area section-padding">
      <div className="container">
        <div className="section-title">
          <h2>
            Des repères clairs
            <br />
            pour avancer sereinement
          </h2>
        </div>
        <div className="row align-items-center">
          <div className="col-lg-6">
            <div className="ab_img">
              <img src="/assets/img/review.png" className="img-fluid" alt="" />
            </div>
          </div>
          <div className="col-lg-6">
            <div className="testimonial">
              <img src="/assets/img/quote.png" alt="" />
              <div className="testimonial_content" aria-live="polite">
                <h3>{title}</h3>
                <p>{text}</p>
              </div>
              <div className="testi_pic_title">
                <h3>{label}</h3>
                <p>Les engagements du projet Nexora</p>
              </div>
            </div>
            <div className="benefit-controls">
              <button
                aria-label="Bénéfice précédent"
                onClick={() =>
                  setCurrent((current + benefits.length - 1) % benefits.length)
                }
              >
                ←
              </button>
              <span>
                {current + 1} / {benefits.length}
              </span>
              <button
                aria-label="Bénéfice suivant"
                onClick={() => setCurrent((current + 1) % benefits.length)}
              >
                →
              </button>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
export function GettingStarted() {
  return (
    <section className="blog_area section-padding">
      <div className="container">
        <div className="section-title text-center">
          <h2>Vos premiers pas dans le Hub</h2>
          <p>
            Quelques repères pour rejoindre votre espace et commencer votre
            parcours.
          </p>
        </div>
        <div className="row">
          {[
            ["Créer votre compte", "/inscription", "S’inscrire"],
            ["Rejoindre vos groupes pédagogiques", "/connexion", "Mon espace"],
            [
              "Consulter vos séances et votre suivi",
              "/connexion",
              "Se connecter",
            ],
          ].map(([title, path, label], i) => (
            <div className="col-lg-4 col-sm-4" key={title}>
              <article className="single_blog">
                <img
                  src={"/assets/img/blog/" + (i + 1) + ".jpg"}
                  className="img-fluid"
                  alt=""
                />
                <div className="content_box">
                  <span>Étape 0{i + 1} · Votre parcours</span>
                  <h3>
                    <Link to={path}>{title}</Link>
                  </h3>
                  <Link to={path} className="btn_one">
                    {label} ↗
                  </Link>
                </div>
              </article>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
