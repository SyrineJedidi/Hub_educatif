import { Link, useParams } from "react-router-dom";
const names: Record<string, string> = {
  cours: "Cours et ressources",
  resumes: "Résumés et illustrations",
  assistant: "Assistant pédagogique",
  quiz: "Quiz et progression",
  coaching: "Planification et coaching",
};
export function ComingSoon() {
  const { slug } = useParams();
  return (
    <section className="preparation panel">
      <span className="ti-light-bulb" aria-hidden="true" />
      <p className="eyebrow">LES PROCHAINS CHAPITRES DU HUB</p>
      <h1>{names[slug!] || "Module à venir"}</h1>
      <h2>Fonctionnalité en préparation</h2>
      <p>
        Ce module sera développé sur le socle commun Nexora. Il n’est pas encore
        disponible.
      </p>
      <Link to="/" className="btn_one">
        Revenir à l’accueil ↗
      </Link>
    </section>
  );
}
export function NotFound() {
  return (
    <section className="preparation">
      <img width="320" src="/assets/img/404.svg" alt="" />
      <h1>Cette page est introuvable</h1>
      <p>
        Le lien a peut-être changé. Retrouvez votre chemin depuis l’accueil.
      </p>
      <Link className="btn_one" to="/">
        Retour à l’accueil ↗
      </Link>
    </section>
  );
}
