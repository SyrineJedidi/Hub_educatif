import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../../api/client";
import { Alert } from "../../components/UI";
import { engines } from "../types";

type PlanItem = { id: string; kind: "sheet" | "cards" | "quiz" | "task"; title: string; detail: string; link: string; reason: string };
type Plan = { advice: string; items: PlanItem[]; engine: string; model: string; generated_at: string };
const icons: Record<PlanItem["kind"], string> = { sheet: "ti-book", cards: "ti-layers-alt", quiz: "ti-help-alt", task: "ti-calendar" };

/** Student home: today's revision plan, items found by the platform and ordered by the AI. */
export default function RevisionPlan() {
  const [plan, setPlan] = useState<Plan | null>(null);
  const [error, setError] = useState<unknown>();
  const [busy, setBusy] = useState(true);
  async function load(refresh = false) {
    setBusy(true);
    setError(undefined);
    try {
      setPlan(await api<Plan>("revisions/plan/" + (refresh ? "?refresh=1" : "")));
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  }
  useEffect(() => {
    void load();
  }, []);
  return (
    <section className="panel revision-plan" aria-labelledby="revision-plan-title" aria-busy={busy}>
      <div className="revision-plan-head">
        <div>
          <p className="eyebrow">Mon plan de révision du jour</p>
          <h2 id="revision-plan-title">Par où commencer aujourd’hui ?</h2>
        </div>
        {plan && (
          <span className="revision-plan-engine">
            <span className="ti-wand" aria-hidden="true" />{" "}
            {plan.engine === "rules" ? "Priorités calculées" : `Conseil de ${engines[plan.engine] || plan.engine}`}
          </span>
        )}
      </div>
      <Alert error={error} />
      {busy && !plan ? (
        <p className="notice" role="status">Préparation de ton plan…</p>
      ) : plan ? (
        <>
          <p className="revision-plan-advice">{plan.advice}</p>
          {plan.items.length > 0 && (
            <ol className="revision-plan-items">
              {plan.items.map((item) => (
                <li key={item.id}>
                  <span className={"revision-plan-icon " + icons[item.kind]} aria-hidden="true" />
                  <div>
                    <Link to={item.link}>{item.title}</Link>
                    <small>{item.reason}</small>
                  </div>
                </li>
              ))}
            </ol>
          )}
          <button className="text-button" onClick={() => void load(true)} disabled={busy}>
            {busy ? "Mise à jour…" : "Actualiser mon plan"}
          </button>
        </>
      ) : null}
    </section>
  );
}
