import { useEffect, useState } from "react";
import {
  Link,
  useNavigate,
  useParams,
  useSearchParams,
} from "react-router-dom";
import { api, date } from "../../api/client";
import { useResource } from "../../hooks/useResource";
import { Alert, Loading, Modal } from "../../components/UI";
import type { AIJob, Sheet } from "../types";
import { engines, seconds, statusLabel } from "../types";
import { AiBadge, PinButton } from "../components/SheetCard";
import Markdown from "../components/Markdown";
import GeneratePanel from "../components/GeneratePanel";
import SelfQuiz from "../components/SelfQuiz";
import Illustrations, { IllustrationDialog } from "../components/Illustrations";
import {
  RatingStars,
  RunningBanner,
  StudioButton,
  StudioDrawer,
} from "../components/AIStudio";
import { useSheetJobs } from "../hooks/useSheetJobs";
import { useSheetContext } from "../hooks/useSheetContext";
import "../styles/revisions.css";
type Action = "publish" | "unpublish" | "archive" | "delete" | "duplicate";
const confirmations: Record<Action, [string, string, string]> = {
  publish: [
    "Publier cette fiche ?",
    "Les étudiants inscrits dans le groupe pourront la consulter, l’imprimer et la copier dans leurs fiches.",
    "Publier la fiche",
  ],
  unpublish: [
    "Repasser en brouillon ?",
    "La fiche ne sera plus visible par les étudiants jusqu’à sa prochaine publication.",
    "Repasser en brouillon",
  ],
  archive: [
    "Archiver cette fiche ?",
    "La fiche est conservée en lecture seule et n’est plus visible par les étudiants. Vous pourrez la restaurer.",
    "Archiver",
  ],
  delete: [
    "Supprimer cette fiche ?",
    "La fiche et ses illustrations seront définitivement supprimées.",
    "Supprimer définitivement",
  ],
  duplicate: [
    "Dupliquer cette fiche ?",
    "Une copie modifiable, illustrations comprises, sera créée en brouillon.",
    "Créer la copie",
  ],
};
export default function SheetDetail() {
  const { id } = useParams(),
    navigate = useNavigate(),
    [params, setParams] = useSearchParams();
  const { base, student, admin } = useSheetContext();
  const { data, error, loading } = useResource<Sheet>("sheets/" + id + "/");
  const [sheet, setSheet] = useState<Sheet | null>(null),
    [action, setAction] = useState<Action | null>(null),
    [generating, setGenerating] = useState(false),
    [illustrating, setIllustrating] = useState(false),
    [studio, setStudio] = useState(false),
    [training, setTraining] = useState(false),
    [busy, setBusy] = useState(false),
    [actionError, setActionError] = useState<unknown>(),
    [notice, setNotice] = useState(""),
    [mastery, setMastery] = useState<number | null>(null);
  useEffect(() => setSheet(data), [data]);
  // Opening a shared sheet counts as a reading for the teacher's follow-up.
  useEffect(() => {
    if (!student || !id) return;
    api<{ mastery: number | null } | null>("sheets/" + id + "/read/", "POST", {})
      .then((progress) => setMastery(progress?.mastery ?? null))
      .catch(() => undefined);
  }, [student, id]);
  function onJobFinished(job: AIJob) {
    if (job.status === "FAILED") {
      setNotice("");
      setActionError(new Error("La génération a échoué : " + job.error));
      return;
    }
    setActionError(undefined);
    if (job.kind === "SUMMARY") {
      api<Sheet>("sheets/" + id + "/")
        .then(setSheet)
        .catch(setActionError);
      setNotice(
        "Résumé rédigé par " +
          (engines[job.engine] || job.engine) +
          " en " +
          seconds(job.duration_ms) +
          (job.fallback ? " (Gemini indisponible : modèle local)" : "") +
          ". Relisez-le puis notez sa pertinence.",
      );
    } else if (job.illustration) {
      const added = job.illustration;
      setSheet((current) =>
        current
          ? {
              ...current,
              illustrations: [
                ...current.illustrations.filter((i) => i.id !== added.id),
                added,
              ],
              illustration_count: current.illustrations.length + 1,
            }
          : current,
      );
      setNotice(
        "Illustration créée par Hugging Face en " +
          seconds(job.duration_ms) +
          " et ajoutée à la galerie.",
      );
    }
  }
  const { jobs, track, replace, running } = useSheetJobs(
    id,
    !!data?.can_edit,
    onJobFinished,
  );
  useEffect(() => {
    if (sheet) document.title = sheet.title + " — Fiches de révision · Nexora";
  }, [sheet]);
  useEffect(() => {
    if (params.get("generer") === "1" && sheet?.can_edit) {
      setGenerating(true);
      setParams({}, { replace: true });
    }
  }, [params, sheet, setParams]);
  if (loading && !sheet) return <Loading />;
  if (error || !sheet)
    return (
      <div className="sheets-module">
        <Alert error={error || "Fiche introuvable."} />
        <Link className="text-button" to={base}>
          ← Retour aux fiches
        </Link>
      </div>
    );
  const editable = sheet.can_edit && sheet.status !== "ARCHIVED";
  const canGenerate = editable && sheet.status === "DRAFT";
  const copyLabel =
    student && !sheet.can_edit ? "Ajouter à mes fiches" : "Dupliquer";
  async function run(kind: Action) {
    setBusy(true);
    setActionError(undefined);
    try {
      if (kind === "delete") {
        await api("sheets/" + sheet!.id + "/", "DELETE");
        navigate(base, { replace: true });
        return;
      }
      const result = await api<Sheet>(
        "sheets/" + sheet!.id + "/" + kind + "/",
        "POST",
        {},
      );
      setAction(null);
      if (kind === "duplicate") {
        navigate(base + "/" + result.id, { replace: false });
        return;
      }
      setSheet(result);
      setNotice(
        kind === "publish"
          ? "La fiche est publiée pour le groupe."
          : kind === "archive"
            ? "La fiche est archivée."
            : "La fiche est de nouveau en brouillon.",
      );
    } catch (err) {
      setActionError(err);
    } finally {
      setBusy(false);
    }
  }
  async function markReviewed() {
    setBusy(true);
    try {
      setSheet(
        await api<Sheet>("sheets/" + sheet!.id + "/", "PATCH", {
          ai_reviewed: true,
        }),
      );
      setNotice("Merci ! Le contenu est marqué comme relu.");
    } catch (err) {
      setActionError(err);
    } finally {
      setBusy(false);
    }
  }
  const summaryRunning = running.some((j) => j.kind === "SUMMARY");
  const pendingImages = running.filter((j) => j.kind === "ILLUSTRATION").length;
  const lastSummary = jobs.find(
    (j) => j.kind === "SUMMARY" && j.status === "SUCCEEDED",
  );
  const blockedReason = !sheet.can_edit
    ? undefined
    : sheet.status === "ARCHIVED"
      ? "Fiche archivée : restaurez-la pour utiliser l’IA."
      : sheet.status === "PUBLISHED"
        ? "Fiche publiée : repassez-la en brouillon pour régénérer le résumé (il devra être relu)."
        : summaryRunning
          ? "Un résumé est déjà en cours de rédaction."
          : undefined;
  function started(job: AIJob) {
    track(job);
    setGenerating(false);
    setIllustrating(false);
    setActionError(undefined);
    setNotice("");
  }
  const showBlockers =
    sheet.can_edit && sheet.status === "DRAFT" && !sheet.personal;
  const empty = !sheet.summary.trim() && !sheet.key_points.length;
  return (
    <div className="sheets-module sheet-page" data-color={sheet.color}>
      <nav className="sheet-back no-print" aria-label="Retour">
        <Link to={base}>
          <span className="ti-arrow-left" aria-hidden="true" /> Toutes les
          fiches
        </Link>
      </nav>
      <header className="sheet-header">
        <div className="sheet-header-main">
          <p className="sheet-course">{sheet.course_label}</p>
          <h1>{sheet.title}</h1>
          <div className="sheet-chips">
            <span className={"sheet-chip status-" + sheet.status.toLowerCase()}>
              {statusLabel(sheet)}
            </span>
            <AiBadge sheet={sheet} />
            {sheet.tags.map((tag) => (
              <span className="sheet-chip tag" key={tag}>
                #{tag}
              </span>
            ))}
          </div>
          <p className="sheet-meta">
            <span>
              <span className="ti-user" aria-hidden="true" /> {sheet.owner_name}
            </span>
            <span>
              <span className="ti-folder" aria-hidden="true" />{" "}
              {sheet.personal ? "Fiche personnelle" : sheet.learning_group_name}
            </span>
            <span>
              <span className="ti-time" aria-hidden="true" /> Mise à jour le{" "}
              {date(sheet.updated_at)}
            </span>
          </p>
        </div>
        <div className="sheet-header-side no-print">
          <PinButton
            sheet={sheet}
            onChange={(pinned) => setSheet({ ...sheet, pinned })}
          />
        </div>
        <div className="sheet-toolbar no-print">
          {sheet.key_points.length + sheet.glossary.length > 0 && (
            <Link
              className={student ? "btn_one" : "sheets-ghost-button"}
              to={base + "/" + sheet.id + "/reviser"}
            >
              <span className="ti-layers-alt" aria-hidden="true" /> Réviser
              avec les cartes
              {mastery !== null && (
                <span className="sheets-mastery">
                  {Math.round(mastery * 100)} % maîtrisé
                </span>
              )}
            </Link>
          )}
          {(sheet.summary.trim().length >= 40 || sheet.key_points.length > 0) && (
            <button className="sheets-ghost-button" onClick={() => setTraining(true)}>
              <span className="ti-help-alt" aria-hidden="true" /> Quiz d’entraînement IA
            </button>
          )}
          {editable && (
            <Link
              className="sheets-ghost-button"
              to={base + "/" + sheet.id + "/modifier"}
            >
              <span className="ti-pencil-alt" aria-hidden="true" /> Modifier
            </Link>
          )}
          {editable && (
            <button
              className="sheets-ai-button"
              onClick={() => setStudio(true)}
            >
              <span className="ti-wand" aria-hidden="true" /> Studio IA
              {running.length > 0 && (
                <span className="sheets-ai-count">{running.length}</span>
              )}
            </button>
          )}
          <a
            className="sheets-ghost-button"
            href={"/api/sheets/" + sheet.id + "/export/"}
            download
          >
            <span className="ti-download" aria-hidden="true" /> Markdown
          </a>
          <button
            className="sheets-ghost-button"
            onClick={() => window.print()}
          >
            <span className="ti-printer" aria-hidden="true" /> Imprimer / PDF
          </button>
          <button
            className="sheets-ghost-button"
            onClick={() => setAction("duplicate")}
          >
            <span className="ti-files" aria-hidden="true" /> {copyLabel}
          </button>
          {sheet.can_edit && (
            <span className="sheet-toolbar-status">
              {sheet.status === "DRAFT" && !sheet.personal && (
                <button
                  className="btn_one"
                  onClick={() => setAction("publish")}
                >
                  <span className="ti-share" aria-hidden="true" /> Publier
                </button>
              )}
              {sheet.status === "PUBLISHED" && (
                <button
                  className="text-button"
                  onClick={() => setAction("unpublish")}
                >
                  Repasser en brouillon
                </button>
              )}
              {sheet.status === "ARCHIVED" ? (
                <button
                  className="text-button"
                  onClick={() => setAction("unpublish")}
                >
                  Restaurer en brouillon
                </button>
              ) : (
                <button
                  className="text-button"
                  onClick={() => setAction("archive")}
                >
                  Archiver
                </button>
              )}
              {sheet.status !== "PUBLISHED" && (
                <button
                  className="text-button danger"
                  onClick={() => setAction("delete")}
                >
                  Supprimer
                </button>
              )}
            </span>
          )}
        </div>
      </header>
      {running.map((job) => (
        <RunningBanner key={job.id} job={job} />
      ))}
      <div className="no-print">
        <Alert error={actionError} success={notice} />
      </div>
      {sheet.ai_generated && sheet.can_edit && !sheet.ai_reviewed && (
        <section
          className="sheet-review no-print"
          aria-labelledby="review-title"
        >
          <span className="ti-wand" aria-hidden="true" />
          <div>
            <h2 id="review-title">
              Contenu généré par l’IA — relecture requise
            </h2>
            <p>
              Généré avec <strong>{sheet.ai_model}</strong>
              {sheet.generated_at && <> le {date(sheet.generated_at)}</>}
              {sheet.source_name && <> à partir de « {sheet.source_name} »</>}.
              Vérifiez l’exactitude du résumé, des points clés et des
              définitions, corrigez-les si besoin, puis confirmez votre
              relecture{sheet.personal ? "." : " avant de publier."}
            </p>
          </div>
          <div className="sheet-review-actions">
            <button
              className="btn_one"
              disabled={busy}
              onClick={() => void markReviewed()}
            >
              J’ai relu ce contenu
            </button>
            {lastSummary && !admin && (
              <RatingStars job={lastSummary} onRated={replace} />
            )}
          </div>
        </section>
      )}
      {showBlockers && (
        <section
          className={
            "sheet-readiness no-print" +
            (sheet.publication_blockers.length ? " has-blockers" : "")
          }
          aria-label="Préparation de la publication"
        >
          {sheet.publication_blockers.length ? (
            <>
              <h2>
                <span className="ti-flag-alt" aria-hidden="true" /> Avant de
                publier
              </h2>
              <ul>
                {sheet.publication_blockers.map((reason) => (
                  <li key={reason}>{reason}</li>
                ))}
              </ul>
            </>
          ) : (
            <h2>
              <span className="ti-check" aria-hidden="true" /> Cette fiche est
              prête à être publiée pour {sheet.learning_group_name}.
            </h2>
          )}
        </section>
      )}
      {empty ? (
        <section className="sheet-empty-content">
          <div className="ai-orb" aria-hidden="true">
            <span className="ti-wand" />
          </div>
          <h2>Cette fiche attend son contenu</h2>
          <p>
            {canGenerate
              ? "Collez votre cours ou importez un PDF : l’IA rédige le résumé, les points clés et le glossaire en arrière-plan pendant que vous continuez à travailler."
              : "Le résumé n’a pas encore été rédigé."}
          </p>
          {canGenerate && (
            <div className="actions">
              <button
                className="btn_one"
                disabled={summaryRunning}
                onClick={() => setGenerating(true)}
              >
                <span className="ti-wand" aria-hidden="true" />{" "}
                {summaryRunning ? "Rédaction en cours…" : "Générer avec l’IA"}
              </button>
              <Link
                className="text-button"
                to={base + "/" + sheet.id + "/modifier"}
              >
                ou rédiger moi-même
              </Link>
            </div>
          )}
        </section>
      ) : (
        <div className="sheet-layout">
          <article className="sheet-main">
            <section className="sheet-section" aria-labelledby="sheet-summary">
              <div className="sheet-section-heading">
                <h2 id="sheet-summary">
                  <span className="ti-book" aria-hidden="true" /> Résumé
                </h2>
              </div>
              {sheet.summary.trim() ? (
                <Markdown text={sheet.summary} />
              ) : (
                <p className="field-help">Aucun résumé rédigé.</p>
              )}
              {sheet.ai_generated && sheet.ai_reviewed && (
                <p className="sheet-provenance">
                  <span className="ti-wand" aria-hidden="true" /> Rédigé avec
                  l’aide de {sheet.ai_model || "Gemini"}, relu par{" "}
                  {sheet.owner_name}.
                </p>
              )}
            </section>
            <Illustrations
              sheet={sheet}
              editable={editable}
              pending={pendingImages}
              onGenerate={() => setIllustrating(true)}
              onChange={(illustrations) =>
                setSheet({
                  ...sheet,
                  illustrations,
                  illustration_count: illustrations.length,
                })
              }
            />
          </article>
          <aside className="sheet-aside">
            <section
              className="sheet-section sheet-keypoints"
              aria-labelledby="sheet-points"
            >
              <h2 id="sheet-points">
                <span className="ti-star" aria-hidden="true" /> À retenir
              </h2>
              {sheet.key_points.length ? (
                <ol>
                  {sheet.key_points.map((point, i) => (
                    <li key={i}>{point}</li>
                  ))}
                </ol>
              ) : (
                <p className="field-help">Aucun point clé.</p>
              )}
            </section>
            {!!sheet.glossary.length && (
              <section
                className="sheet-section sheet-glossary"
                aria-labelledby="sheet-glossary"
              >
                <h2 id="sheet-glossary">
                  <span className="ti-bookmark-alt" aria-hidden="true" />{" "}
                  Glossaire
                </h2>
                <dl>
                  {sheet.glossary.map((entry) => (
                    <div key={entry.term}>
                      <dt>{entry.term}</dt>
                      <dd>{entry.definition}</dd>
                    </div>
                  ))}
                </dl>
              </section>
            )}
          </aside>
        </div>
      )}
      <p className="sheet-print-footer">
        Hub Éducatif Multimodal · Nexora — {sheet.title} · {sheet.course_label}
      </p>
      {generating && (
        <GeneratePanel
          sheet={sheet}
          onClose={() => setGenerating(false)}
          onStarted={started}
        />
      )}
      {illustrating && (
        <IllustrationDialog
          sheet={sheet}
          onClose={() => setIllustrating(false)}
          onStarted={started}
        />
      )}
      {sheet.can_edit && (
        <StudioButton
          running={running.length}
          onClick={() => setStudio(true)}
        />
      )}
      {training && <SelfQuiz sheetId={sheet.id} onClose={() => setTraining(false)} />}
      {studio && (
        <StudioDrawer
          jobs={jobs}
          canSummarize={canGenerate && !summaryRunning}
          canIllustrate={
            editable && sheet.illustrations.length + pendingImages < 12
          }
          blockedReason={blockedReason}
          canRate={!admin}
          onClose={() => setStudio(false)}
          onSummarize={() => {
            setStudio(false);
            setGenerating(true);
          }}
          onIllustrate={() => {
            setStudio(false);
            setIllustrating(true);
          }}
          onRated={replace}
        />
      )}
      {action && (
        <Modal
          title={confirmations[action][0]}
          onClose={() => !busy && setAction(null)}
        >
          <p className="intro">{confirmations[action][1]}</p>
          <Alert error={actionError} />
          <div className="actions">
            <button
              className="btn_one"
              disabled={busy}
              onClick={() => void run(action)}
            >
              {busy ? "Veuillez patienter…" : confirmations[action][2]}
            </button>
            <button
              className="text-button"
              onClick={() => setAction(null)}
              disabled={busy}
            >
              Annuler
            </button>
          </div>
        </Modal>
      )}
    </div>
  );
}
