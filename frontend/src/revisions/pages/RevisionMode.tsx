import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../../api/client";
import { useResource } from "../../hooks/useResource";
import { Alert, Loading } from "../../components/UI";
import type { Sheet } from "../types";
import { percent } from "../types";
import { useSheetContext } from "../hooks/useSheetContext";
import "../styles/revision.css";
interface Card {
  id: string;
  kind: "TERM" | "POINT";
  front: string;
  back: string;
}
interface Progress {
  views: number;
  review_sessions: number;
  known: string[];
  mastery: number | null;
}
interface Deck {
  cards: Card[];
  tracked: boolean;
  progress: Progress;
}
const shuffle = <T,>(items: T[]) => {
  const copy = [...items];
  for (let i = copy.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [copy[i], copy[j]] = [copy[j], copy[i]];
  }
  return copy;
};
/** Flashcard revision of a sheet: glossary terms and key points, with saved mastery. */
export default function RevisionMode() {
  const { id } = useParams();
  const { base } = useSheetContext();
  const sheet = useResource<Sheet>("sheets/" + id + "/");
  const deck = useResource<Deck>("sheets/" + id + "/cards/");
  const [order, setOrder] = useState<Card[]>([]),
    [index, setIndex] = useState(0),
    [flipped, setFlipped] = useState(false),
    [known, setKnown] = useState<string[]>([]),
    [answers, setAnswers] = useState<Record<string, boolean>>({}),
    [result, setResult] = useState<{ saved: boolean; mastery: number | null } | null>(null),
    [saving, setSaving] = useState(false),
    [error, setError] = useState<unknown>();
  const cardRef = useRef<HTMLButtonElement>(null);
  function start(cards: Card[]) {
    setOrder(cards);
    setIndex(0);
    setFlipped(false);
    setAnswers({});
    setResult(null);
  }
  useEffect(() => {
    if (!deck.data) return;
    setKnown(deck.data.progress.known);
    start(deck.data.cards);
  }, [deck.data]);
  const toReview = useMemo(
    () => (deck.data?.cards || []).filter((c) => !known.includes(c.id)),
    [deck.data, known],
  );
  async function finish(final: Record<string, boolean>) {
    // Cards answered « Je savais » are kept, the others are removed from the known set.
    const next = new Set(known);
    Object.entries(final).forEach(([cardId, ok]) => (ok ? next.add(cardId) : next.delete(cardId)));
    setSaving(true);
    try {
      const saved = await api<{ saved: boolean; known: string[]; mastery: number | null }>(
        "sheets/" + id + "/review/",
        "POST",
        { known: [...next] },
      );
      setKnown(saved.known);
      setResult({ saved: saved.saved, mastery: saved.mastery });
    } catch (err) {
      setError(err);
    } finally {
      setSaving(false);
    }
  }
  function answer(ok: boolean) {
    const card = order[index];
    const final = { ...answers, [card.id]: ok };
    setAnswers(final);
    setFlipped(false);
    if (index + 1 < order.length) {
      setIndex(index + 1);
      requestAnimationFrame(() => cardRef.current?.focus());
    } else void finish(final);
  }
  useEffect(() => {
    const keys = (e: KeyboardEvent) => {
      if (result || !order.length || (e.target as HTMLElement).closest("input, textarea, select")) return;
      if (e.key === " " && document.activeElement === cardRef.current) return;
      if (e.key === "ArrowRight" && flipped) answer(true);
      else if (e.key === "ArrowLeft" && flipped) answer(false);
    };
    window.addEventListener("keydown", keys);
    return () => window.removeEventListener("keydown", keys);
  });
  if ((sheet.loading && !sheet.data) || (deck.loading && !deck.data)) return <Loading />;
  if (sheet.error || deck.error || !sheet.data || !deck.data)
    return <Alert error={sheet.error || deck.error || "Fiche introuvable."} />;
  const card = order[index];
  const done = Object.keys(answers).length;
  const right = Object.values(answers).filter(Boolean).length;
  return (
    <div className="rv-page">
      <nav className="rv-back" aria-label="Retour">
        <Link to={base + "/" + id}>
          <span className="ti-arrow-left" aria-hidden="true" /> Retour à la fiche
        </Link>
      </nav>
      <header className="rv-head">
        <div>
          <p className="rv-eyebrow">Mode révision · {sheet.data.course_label}</p>
          <h1>{sheet.data.title}</h1>
          <p>
            Lisez la carte, essayez de vous souvenir de la réponse, retournez-la
            puis dites honnêtement si vous saviez.{" "}
            {deck.data.tracked
              ? "Votre progression est enregistrée et visible par votre enseignant."
              : "Session d’entraînement : rien n’est enregistré."}
          </p>
        </div>
        <dl className="rv-stats">
          <div>
            <dt>Cartes</dt>
            <dd>{deck.data.cards.length}</dd>
          </div>
          <div>
            <dt>Maîtrisées</dt>
            <dd>{known.length}</dd>
          </div>
          <div>
            <dt>Maîtrise</dt>
            <dd>{percent(deck.data.cards.length ? known.length / deck.data.cards.length : null)}</dd>
          </div>
        </dl>
      </header>
      {!deck.data.cards.length ? (
        <p className="notice">Cette fiche n’a encore ni point clé ni glossaire : il n’y a rien à réviser.</p>
      ) : result ? (
        <section className="rv-result" aria-labelledby="rv-result-title" role="status">
          <span className="rv-result-icon" aria-hidden="true">
            <span className={right === done ? "ti-crown" : "ti-medall"} />
          </span>
          <h2 id="rv-result-title">
            {right} carte{right > 1 ? "s" : ""} sur {done} connue{right > 1 ? "s" : ""}
          </h2>
          <p>
            Maîtrise de la fiche : <strong>{percent(result.mastery)}</strong>.{" "}
            {result.saved ? "Progression enregistrée." : "Session d’entraînement non enregistrée."}
          </p>
          <div className="rv-actions">
            {toReview.length > 0 && (
              <button type="button" className="btn_one" onClick={() => start(shuffle(toReview))}>
                <span className="ti-reload" aria-hidden="true" /> Revoir les {toReview.length} carte
                {toReview.length > 1 ? "s" : ""} à travailler
              </button>
            )}
            <button type="button" className="rv-ghost" onClick={() => start(shuffle(deck.data!.cards))}>
              <span className="ti-loop" aria-hidden="true" /> Tout recommencer (mélangé)
            </button>
            <Link className="rv-ghost" to={base + "/" + id}>
              Relire la fiche
            </Link>
          </div>
        </section>
      ) : (
        <section className="rv-session" aria-label="Session de révision">
          <div className="rv-progress">
            <span>
              Carte {index + 1} sur {order.length}
            </span>
            <progress max={order.length} value={done} aria-label="Avancement de la session" />
            <button type="button" className="rv-link" onClick={() => start(shuffle(order))}>
              <span className="ti-shuffle" aria-hidden="true" /> Mélanger
            </button>
          </div>
          <button
            ref={cardRef}
            type="button"
            className={"rv-card" + (flipped ? " is-flipped" : "") + (card.kind === "TERM" ? " is-term" : "")}
            onClick={() => setFlipped(!flipped)}
            aria-live="polite"
            aria-label={flipped ? "Réponse : " + card.back + ". Cliquez pour revoir la question." : card.front + ". Cliquez pour voir la réponse."}
          >
            <span className="rv-face rv-front" aria-hidden={flipped}>
              <small>{card.kind === "TERM" ? "Que signifie ce terme ?" : "Que faut-il retenir ?"}</small>
              <strong>{card.front}</strong>
              <em>Cliquez ou appuyez sur Entrée pour retourner la carte</em>
            </span>
            <span className="rv-face rv-back-face" aria-hidden={!flipped}>
              <small>{card.front}</small>
              <strong>{card.back}</strong>
            </span>
          </button>
          <div className="rv-answer" role="group" aria-label="Votre réponse">
            <button type="button" className="rv-no" onClick={() => answer(false)} disabled={!flipped || saving}>
              <span className="ti-back-left" aria-hidden="true" /> À revoir
              <small>Flèche gauche</small>
            </button>
            <button type="button" className="rv-yes" onClick={() => answer(true)} disabled={!flipped || saving}>
              <span className="ti-check" aria-hidden="true" /> Je savais
              <small>Flèche droite</small>
            </button>
          </div>
          {!flipped && <p className="rv-hint">Retournez la carte pour répondre.</p>}
        </section>
      )}
      <Alert error={error} />
    </div>
  );
}
