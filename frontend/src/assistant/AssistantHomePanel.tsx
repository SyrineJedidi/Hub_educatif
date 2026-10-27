import { Link } from "react-router-dom";
import { useResource } from "../hooks/useResource";
import type { Page } from "../api/types";
import { reviewsPath } from "./api";
import type { Review } from "./types";
import "./assistant.css";

// The home page's access cards sit in a fixed three-column grid, so the assistant gets its own panel below them.
export default function AssistantHomePanel({ teacher }: { teacher: boolean }) {
  return teacher ? <TeacherPanel /> : <StudentPanel />;
}

function TeacherPanel() {
  const reviews = useResource<Page<Review>>(
    reviewsPath({ status: "NEW", scope: "", reason: "", page: 1 }),
  );
  const pending = reviews.data?.count ?? 0;
  return (
    <section
      className="panel assistant-home"
      aria-labelledby="assistant-home-title"
    >
      <div className="assistant-home-intro">
        <span className="ti-comments sc_four" aria-hidden="true" />
        <div>
          <p className="eyebrow">ASSISTANT PÉDAGOGIQUE</p>
          <h2 id="assistant-home-title">
            Accompagner vos étudiants avec l’assistant
          </h2>
          <p>
            Rédigez les notes dont il se sert, réglez-le pour chaque groupe,
            suivez son utilisation et traitez les réponses que vos étudiants
            vous signalent.
          </p>
        </div>
      </div>
      <nav className="assistant-home-links" aria-label="Pages de l’assistant">
        <Link to="/espace/assistant/signalements">
          Signalements
          {pending > 0 && ` · ${pending} à traiter`}
        </Link>
        <Link to="/espace/assistant/notes">Notes de cours</Link>
        <Link to="/espace/assistant/parametres">Paramètres</Link>
        <Link to="/espace/assistant/suivi">Suivi</Link>
        <Link to="/espace/assistant">Tester l’assistant ↗</Link>
      </nav>
    </section>
  );
}

function StudentPanel() {
  return (
    <section
      className="panel assistant-home"
      aria-labelledby="assistant-home-title"
    >
      <div className="assistant-home-intro">
        <span className="ti-comments sc_four" aria-hidden="true" />
        <div>
          <p className="eyebrow">ASSISTANT PÉDAGOGIQUE</p>
          <h2 id="assistant-home-title">Une question sur votre cours ?</h2>
          <p>
            Posez-la par écrit ou à voix haute : l’assistant répond à partir de
            votre cours, avec ses sources.
          </p>
        </div>
      </div>
      <Link className="btn_one" to="/espace/assistant">
        Poser une question ↗
      </Link>
    </section>
  );
}
