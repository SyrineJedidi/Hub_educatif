import { useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../../api/client";
import type { SheetSummary } from "../types";
import { statusLabel } from "../types";
const day = (value: string) =>
  new Intl.DateTimeFormat("fr-FR", {
    dateStyle: "medium",
    timeZone: "Africa/Tunis",
  }).format(new Date(value));
export function AiBadge({ sheet }: { sheet: SheetSummary }) {
  if (!sheet.ai_generated) return null;
  return (
    <span className={"sheet-chip ai" + (sheet.ai_reviewed ? "" : " pending")}>
      <span className="ti-wand" aria-hidden="true" />
      {sheet.ai_reviewed ? "IA · relue" : "IA · à relire"}
    </span>
  );
}
export function PinButton({
  sheet,
  onChange,
}: {
  sheet: SheetSummary;
  onChange: (pinned: boolean) => void;
}) {
  const [busy, setBusy] = useState(false);
  if (!sheet.can_edit) return null;
  async function toggle() {
    setBusy(true);
    try {
      await api("sheets/" + sheet.id + "/", "PATCH", { pinned: !sheet.pinned });
      onChange(!sheet.pinned);
    } finally {
      setBusy(false);
    }
  }
  return (
    <button
      type="button"
      className={"sheet-pin" + (sheet.pinned ? " is-pinned" : "")}
      aria-pressed={sheet.pinned}
      aria-label={
        (sheet.pinned ? "Désépingler « " : "Épingler « ") + sheet.title + " »"
      }
      title={sheet.pinned ? "Désépingler" : "Épingler en haut de la liste"}
      disabled={busy}
      onClick={() => void toggle().catch(() => undefined)}
    >
      <span className="ti-pin-alt" aria-hidden="true" />
    </button>
  );
}
export default function SheetCard({
  sheet,
  base,
  userId,
  onPinned,
}: {
  sheet: SheetSummary;
  base: string;
  userId?: string;
  onPinned: (pinned: boolean) => void;
}) {
  return (
    <article
      className={"sheet-card" + (sheet.pinned ? " is-pinned" : "")}
      data-color={sheet.color}
    >
      <div className="sheet-card-cover" aria-hidden="true">
        {sheet.cover_url ? (
          <img src={sheet.cover_url} alt="" loading="lazy" />
        ) : (
          <span className="sheet-card-monogram">
            {sheet.course_label.charAt(0).toUpperCase()}
          </span>
        )}
      </div>
      <PinButton sheet={sheet} onChange={onPinned} />
      <div className="sheet-card-body">
        <p className="sheet-course">{sheet.course_label}</p>
        <h2>
          <Link to={base + "/" + sheet.id}>{sheet.title}</Link>
        </h2>
        <p className="sheet-excerpt">
          {sheet.excerpt || "Cette fiche attend encore son résumé."}
        </p>
        <div className="sheet-chips">
          <span className={"sheet-chip status-" + sheet.status.toLowerCase()}>
            {statusLabel(sheet)}
          </span>
          <AiBadge sheet={sheet} />
          {sheet.tags.slice(0, 3).map((tag) => (
            <span className="sheet-chip tag" key={tag}>
              #{tag}
            </span>
          ))}
          {sheet.tags.length > 3 && (
            <span className="sheet-chip tag">+{sheet.tags.length - 3}</span>
          )}
        </div>
        <dl className="sheet-card-meta">
          <div>
            <dt>Points clés</dt>
            <dd>{sheet.key_point_count}</dd>
          </div>
          <div>
            <dt>Illustrations</dt>
            <dd>{sheet.illustration_count}</dd>
          </div>
          <div>
            <dt>{sheet.personal ? "Espace" : "Groupe"}</dt>
            <dd>{sheet.personal ? "Personnel" : sheet.learning_group_name}</dd>
          </div>
        </dl>
        <p className="sheet-card-footer">
          <span>
            {sheet.owner_id === userId ? "Par vous" : sheet.owner_name}
          </span>
          <span>Mise à jour le {day(sheet.updated_at)}</span>
        </p>
      </div>
    </article>
  );
}
