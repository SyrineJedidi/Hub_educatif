import { useEffect, useRef, useState } from "react";
import type { FormEvent } from "react";
import { Link } from "react-router-dom";
import { allPages, api } from "../../api/client";
import type { Group } from "../../api/types";
import { Alert } from "../../components/UI";
import type { AIJob, Sheet, SheetSummary } from "../types";
import { engines, percent, seconds, summaryLengths } from "../types";
import { RatingStars, useAIStatus, useElapsed } from "../components/AIStudio";
import { useSheetContext } from "../hooks/useSheetContext";
import "../styles/revisions.css";
import "../styles/studio.css";
import "../styles/backoffice.css";
type Length = keyof typeof summaryLengths;
const words = (text: string) => (text.trim() ? text.trim().split(/\s+/).length : 0);
function useJob(initial: AIJob | null) {
  const [job, setJob] = useState(initial);
  useEffect(() => setJob(initial), [initial]);
  const active = job && (job.status === "QUEUED" || job.status === "RUNNING");
  useEffect(() => {
    if (!job || !active) return;
    const timer = window.setTimeout(() => {
      api<AIJob>("ai/jobs/" + job.id + "/").then(setJob).catch(() => undefined);
    }, 1500);
    return () => window.clearTimeout(timer);
  }, [job, active]);
  return [job, setJob] as const;
}
function Step({
  state,
  title,
  children,
}: {
  state: "done" | "active" | "waiting" | "failed";
  title: string;
  children?: React.ReactNode;
}) {
  const icon = { done: "ti-check", active: "ti-reload", waiting: "ti-time", failed: "ti-close" }[state];
  const label = { done: "terminé", active: "en cours", waiting: "en attente", failed: "échec" }[state];
  return (
    <li className={"wk-step is-" + state}>
      <span className="wk-step-dot" aria-hidden="true">
        <span className={icon} />
      </span>
      <div>
        <strong>
          {title} <span className="sr-only">({label})</span>
        </strong>
        {children}
      </div>
    </li>
  );
}
function JobStep({ job, title }: { job: AIJob; title: string }) {
  const elapsed = useElapsed(job);
  const state =
    job.status === "SUCCEEDED" ? "done" : job.status === "FAILED" ? "failed" : "active";
  return (
    <Step state={state} title={title}>
      {state === "active" && (
        <>
          <span className="wk-step-text">
            {job.status === "QUEUED"
              ? "Dans la file d’attente du worker Celery…"
              : "Le modèle travaille…"}{" "}
            {seconds(elapsed)}
          </span>
          <span className="wk-progress" aria-hidden="true" />
        </>
      )}
      {state === "done" && (
        <span className="wk-step-text">
          {(engines[job.engine] || job.engine) + " · " + job.model.split("/").pop()} ·{" "}
          {seconds(job.duration_ms)}
          {job.fallback && " · Gemini indisponible, modèle local utilisé"}
        </span>
      )}
      {state === "failed" && <span className="wk-step-text wk-error">{job.error}</span>}
    </Step>
  );
}
/** Guided page: from a course to a reviewed revision sheet, with the AI. */
export default function AIWorkshop() {
  const { admin, student, base, paths } = useSheetContext();
  const status = useAIStatus();
  const [mode, setMode] = useState<"text" | "file">("text"),
    [text, setText] = useState(""),
    [file, setFile] = useState<File | null>(null),
    [target, setTarget] = useState<"new" | "existing">("new"),
    [title, setTitle] = useState(""),
    [courseLabel, setCourseLabel] = useState(""),
    [groupId, setGroupId] = useState(""),
    [existingId, setExistingId] = useState(""),
    [length, setLength] = useState<Length>("STANDARD"),
    [withImage, setWithImage] = useState(true),
    [groups, setGroups] = useState<Group[]>([]),
    [drafts, setDrafts] = useState<SheetSummary[]>([]),
    [error, setError] = useState<unknown>(),
    [busy, setBusy] = useState(false),
    [sheet, setSheet] = useState<Sheet | null>(null),
    [accepted, setAccepted] = useState<number | null>(null),
    [startJob, setStartJob] = useState<AIJob | null>(null),
    [imageStart, setImageStart] = useState<AIJob | null>(null);
  const [job, setJob] = useJob(startJob);
  const [imageJob] = useJob(imageStart);
  const fileInput = useRef<HTMLInputElement>(null);
  const progress = useRef<HTMLDivElement>(null);
  const imageRequested = useRef(false);
  useEffect(() => {
    if (!student)
      allPages<Group>("groups/")
        .then((all) => setGroups(all.filter((g) => !g.archived)))
        .catch(setError);
    allPages<SheetSummary>("sheets/?status=DRAFT" + (admin ? "" : "&scope=mine"))
      .then((all) => setDrafts(all.filter((s) => s.can_edit)))
      .catch(setError);
  }, [student, admin]);
  // Once the summary is ready, the illustration is drawn from the idea the AI proposed.
  useEffect(() => {
    if (!sheet || job?.status !== "SUCCEEDED" || !withImage || imageRequested.current) return;
    // Requested once: reloading the sheet below must not start a second illustration.
    imageRequested.current = true;
    api<Sheet>("sheets/" + sheet.id + "/")
      .then((fresh) => {
        setSheet(fresh);
        if (!fresh.illustration_prompt || !status?.illustration) return null;
        return api<AIJob>("sheets/" + sheet.id + "/illustrations/generate/", "POST", {
          prompt: fresh.illustration_prompt,
          style: "SCHEMA",
          caption: "Illustration pédagogique : " + fresh.title,
        }).then(setImageStart);
      })
      .catch(setError);
  }, [job?.status, sheet, withImage, status?.illustration]);
  function pick(files: FileList | null) {
    const chosen = files?.[0];
    if (!chosen) return;
    if (!/\.(pdf|txt|md)$/i.test(chosen.name))
      return setError(new Error("Formats acceptés : PDF, TXT ou Markdown."));
    if (chosen.size > 10 * 1024 * 1024)
      return setError(new Error("La taille maximale est de 10 Mo."));
    setError(undefined);
    setFile(chosen);
    if (!title) setTitle(chosen.name.replace(/\.[^.]+$/, "").replace(/[-_]+/g, " ").slice(0, 120));
  }
  async function submit(e: FormEvent) {
    e.preventDefault();
    if (busy) return;
    setError(undefined);
    if (mode === "text" && text.trim().length < 80)
      return setError(new Error("Étape 1 : collez au moins quelques paragraphes du cours (80 caractères minimum)."));
    if (mode === "file" && !file)
      return setError(new Error("Étape 1 : choisissez un fichier PDF, TXT ou Markdown."));
    if (target === "new" && (!title.trim() || !courseLabel.trim()))
      return setError(new Error("Étape 2 : indiquez le titre de la fiche et le nom du cours."));
    if (target === "new" && !student && !groupId)
      return setError(new Error("Étape 2 : choisissez le groupe qui recevra la fiche."));
    if (target === "existing" && !existingId)
      return setError(new Error("Étape 2 : choisissez la fiche à compléter."));
    setBusy(true);
    try {
      let current: Sheet;
      if (target === "new") {
        const group = groups.find((g) => g.id === groupId);
        current = await api<Sheet>("sheets/", "POST", {
          title: title.trim(),
          course_label: courseLabel.trim(),
          ...(student ? {} : { learning_group_id: groupId }),
          ...(admin && group ? { teacher_id: group.teacher_id } : {}),
        });
      } else current = await api<Sheet>("sheets/" + existingId + "/");
      setSheet(current);
      let body: FormData | Record<string, string>;
      if (mode === "file" && file) {
        body = new FormData();
        body.append("file", file);
        body.append("length", length);
      } else body = { source_text: text, length };
      const sent = performance.now();
      const started = await api<AIJob>("sheets/" + current.id + "/generate/", "POST", body);
      setAccepted(Math.round(performance.now() - sent));
      setStartJob(started);
      requestAnimationFrame(() => progress.current?.focus());
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  }
  function restart() {
    setSheet(null);
    setStartJob(null);
    setImageStart(null);
    imageRequested.current = false;
    setAccepted(null);
    setText("");
    setFile(null);
    setTitle("");
    setError(undefined);
  }
  const finished = job?.status === "SUCCEEDED";
  const imageDone = !withImage || !imageJob || imageJob.status === "SUCCEEDED" || imageJob.status === "FAILED";
  const metrics = job?.metrics || {};
  return (
    <div className="bo-page wk">
      <header className="bo-page-head">
        <div>
          <p className="bo-eyebrow">Résumés et illustrations · Intelligence artificielle</p>
          <h1>Atelier IA</h1>
          <p>
            Transformez un cours en fiche de révision : l’IA rédige le résumé, les
            points clés et le glossaire, puis dessine une illustration. Vous relisez
            tout avant de partager.
          </p>
        </div>
        {!student && (
          <div className="bo-head-actions">
            <Link className="bo-btn" to={paths.journal}>
              <span className="ti-list" aria-hidden="true" /> Journal des générations
            </Link>
          </div>
        )}
      </header>
      <ul className="wk-engines" aria-label="Services d’intelligence artificielle utilisés">
        <li className={status?.summary ? "on" : "off"}>
          <span className="ti-book" aria-hidden="true" />
          <span>
            <small>Résumé</small>
            {status ? status.summary_engine || "Non configuré" : "…"}
          </span>
        </li>
        <li className={status?.fallback_engine ? "on" : "off"}>
          <span className="ti-shield" aria-hidden="true" />
          <span>
            <small>Secours automatique</small>
            {status?.fallback_engine || "Aucun"}
          </span>
        </li>
        <li className={status?.illustration ? "on" : "off"}>
          <span className="ti-image" aria-hidden="true" />
          <span>
            <small>Illustration</small>
            {status ? status.illustration_engine || "Non configurée" : "…"}
          </span>
        </li>
        <li className="on">
          <span className="ti-server" aria-hidden="true" />
          <span>
            <small>Traitement</small>
            {status ? "Arrière-plan · " + status.job_backend : "…"}
          </span>
        </li>
      </ul>
      {!sheet || !job ? (
        <form className="wk-form" onSubmit={submit} noValidate>
          <section className="bo-card wk-block" aria-labelledby="wk-1">
            <h2 id="wk-1">
              <span className="wk-num" aria-hidden="true">1</span> Le cours à résumer
            </h2>
            <div className="sheets-segmented" role="group" aria-label="Source du cours">
              <button type="button" aria-pressed={mode === "text"} onClick={() => setMode("text")}>
                <span className="ti-text" aria-hidden="true" /> Coller le texte
              </button>
              <button type="button" aria-pressed={mode === "file"} onClick={() => setMode("file")}>
                <span className="ti-import" aria-hidden="true" /> Importer un fichier
              </button>
            </div>
            {mode === "text" ? (
              <div className="field">
                <label htmlFor="wk-source">Contenu du cours</label>
                <textarea
                  id="wk-source"
                  className="form-control"
                  rows={10}
                  maxLength={60000}
                  value={text}
                  onChange={(e) => setText(e.target.value)}
                  placeholder="Collez ici le chapitre, vos notes de cours ou une transcription…"
                  aria-describedby="wk-count"
                />
                <p id="wk-count" className="field-help">
                  {words(text).toLocaleString("fr-FR")} mots ·{" "}
                  {text.length.toLocaleString("fr-FR")} / 60 000 caractères
                </p>
              </div>
            ) : (
              <div
                className="sheets-dropzone"
                onDragOver={(e) => e.preventDefault()}
                onDrop={(e) => {
                  e.preventDefault();
                  pick(e.dataTransfer.files);
                }}
              >
                <span className="ti-cloud-up" aria-hidden="true" />
                <p>{file ? <strong>{file.name}</strong> : "Glissez votre support ici"}</p>
                <small>PDF texte, TXT ou Markdown · 10 Mo maximum</small>
                <button type="button" className="bo-btn" onClick={() => fileInput.current?.click()}>
                  {file ? "Choisir un autre fichier" : "Parcourir mes fichiers"}
                </button>
                <input
                  ref={fileInput}
                  type="file"
                  accept=".pdf,.txt,.md,application/pdf,text/plain,text/markdown"
                  hidden
                  onChange={(e) => pick(e.target.files)}
                />
              </div>
            )}
          </section>
          <section className="bo-card wk-block" aria-labelledby="wk-2">
            <h2 id="wk-2">
              <span className="wk-num" aria-hidden="true">2</span> La fiche à remplir
            </h2>
            <div className="sheets-segmented" role="group" aria-label="Fiche de destination">
              <button type="button" aria-pressed={target === "new"} onClick={() => setTarget("new")}>
                <span className="ti-plus" aria-hidden="true" /> Nouvelle fiche
              </button>
              <button
                type="button"
                aria-pressed={target === "existing"}
                onClick={() => setTarget("existing")}
                disabled={!drafts.length}
              >
                <span className="ti-pencil-alt" aria-hidden="true" /> Compléter un brouillon
              </button>
            </div>
            {target === "new" ? (
              <div className="wk-grid">
                <div className="field">
                  <label htmlFor="wk-title">Titre de la fiche</label>
                  <input id="wk-title" className="form-control" maxLength={120} value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Ex. La respiration cellulaire" />
                </div>
                <div className="field">
                  <label htmlFor="wk-course">Cours</label>
                  <input id="wk-course" className="form-control" maxLength={120} value={courseLabel} onChange={(e) => setCourseLabel(e.target.value)} placeholder="Ex. Biologie cellulaire" />
                </div>
                {!student && (
                  <div className="field">
                    <label htmlFor="wk-group">Groupe destinataire</label>
                    <select id="wk-group" className="form-control" value={groupId} onChange={(e) => setGroupId(e.target.value)}>
                      <option value="">Choisir un groupe…</option>
                      {groups.map((g) => (
                        <option key={g.id} value={g.id}>
                          {g.name}
                          {admin ? " — " + g.teacher_name : ""}
                        </option>
                      ))}
                    </select>
                  </div>
                )}
              </div>
            ) : (
              <div className="field">
                <label htmlFor="wk-existing">Brouillon à compléter</label>
                <select id="wk-existing" className="form-control" value={existingId} onChange={(e) => setExistingId(e.target.value)}>
                  <option value="">Choisir une fiche…</option>
                  {drafts.map((d) => (
                    <option key={d.id} value={d.id}>
                      {d.title} — {d.course_label}
                    </option>
                  ))}
                </select>
                <p className="field-help">Le résumé, les points clés et le glossaire actuels seront remplacés.</p>
              </div>
            )}
          </section>
          <section className="bo-card wk-block" aria-labelledby="wk-3">
            <h2 id="wk-3">
              <span className="wk-num" aria-hidden="true">3</span> Ce que l’IA doit produire
            </h2>
            <fieldset className="sheets-choice-grid">
              <legend>Niveau de détail du résumé</legend>
              <div className="sheets-choice-options">
                {Object.entries(summaryLengths).map(([key, [label, help]]) => (
                  <label key={key} className={length === key ? "is-selected" : ""}>
                    <input type="radio" name="wk-length" value={key} checked={length === key} onChange={() => setLength(key as Length)} />
                    <strong>{label}</strong>
                    <small>{help}</small>
                  </label>
                ))}
              </div>
            </fieldset>
            <label className="wk-check">
              <input type="checkbox" checked={withImage} onChange={(e) => setWithImage(e.target.checked)} disabled={status?.illustration === false} />
              <span>
                <strong>Ajouter une illustration générée</strong>
                <small>Dès que le résumé est prêt, Hugging Face dessine l’idée d’image proposée par l’IA.</small>
              </span>
            </label>
          </section>
          <Alert error={error} />
          <div className="wk-submit">
            <button className="bo-btn bo-btn-ai bo-btn-large" type="submit" disabled={busy || status?.summary === false}>
              <span className="ti-wand" aria-hidden="true" /> {busy ? "Envoi du cours…" : "Lancer l’IA"}
            </button>
            <p>La requête répond immédiatement ; la génération continue en arrière-plan.</p>
          </div>
        </form>
      ) : (
        <section className="bo-card wk-run" aria-labelledby="wk-run-title" ref={progress} tabIndex={-1}>
          <h2 id="wk-run-title">
            {finished && imageDone ? "Votre fiche est prête à être relue" : "L’IA prépare votre fiche…"}
          </h2>
          <ol className="wk-steps" aria-live="polite">
            <Step state="done" title={"Fiche « " + sheet.title + " » prête en brouillon"} />
            <Step state="done" title="Cours transmis au serveur">
              <span className="wk-step-text">Réponse 202 Accepted en {accepted} ms : la page n’est jamais bloquée.</span>
            </Step>
            <JobStep job={job} title="Résumé, points clés et glossaire" />
            {withImage &&
              (imageJob ? (
                <JobStep job={imageJob} title="Illustration pédagogique" />
              ) : (
                <Step state={job.status === "FAILED" ? "failed" : "waiting"} title="Illustration pédagogique">
                  <span className="wk-step-text">Démarre dès que le résumé est prêt.</span>
                </Step>
              ))}
            <Step state={finished && imageDone ? "active" : "waiting"} title="Relecture humaine obligatoire avant publication" />
          </ol>
          {finished && (
            <>
              <h3 className="wk-sub">Qualité mesurée de ce résumé</h3>
              <dl className="wk-metrics">
                <div>
                  <dt>Mots-clés du cours couverts</dt>
                  <dd>{percent(metrics.keyword_coverage)}</dd>
                </div>
                <div>
                  <dt>Compression</dt>
                  <dd>{percent(metrics.compression)}</dd>
                </div>
                <div>
                  <dt>Structure respectée</dt>
                  <dd>{percent(metrics.structure_score)}</dd>
                </div>
                <div>
                  <dt>Durée de génération</dt>
                  <dd>{seconds(job.duration_ms)}</dd>
                </div>
                <div>
                  <dt>Points clés · glossaire</dt>
                  <dd>
                    {metrics.key_points ?? "—"} · {metrics.glossary_terms ?? "—"}
                  </dd>
                </div>
              </dl>
              {!!metrics.keywords_missing?.length && (
                <p className="field-help">
                  Notions du cours absentes du résumé : {metrics.keywords_missing.join(", ")}.
                </p>
              )}
              <RatingStars job={job} onRated={setJob} />
              {imageJob?.illustration && (
                <figure className="wk-image">
                  <img src={imageJob.illustration.url} alt={imageJob.illustration.caption} />
                  <figcaption>{imageJob.illustration.caption}</figcaption>
                </figure>
              )}
            </>
          )}
          <Alert error={error} />
          <div className="wk-run-actions">
            <Link className="bo-btn bo-btn-primary" to={base + "/" + sheet.id}>
              <span className="ti-eye" aria-hidden="true" /> {finished ? "Relire et publier la fiche" : "Ouvrir la fiche"}
            </Link>
            {finished && (
              <Link className="bo-btn" to={base + "/" + sheet.id + "/modifier"}>
                <span className="ti-pencil" aria-hidden="true" /> Modifier le contenu
              </Link>
            )}
            <button type="button" className="bo-btn" onClick={restart} disabled={!finished && job.status !== "FAILED"}>
              <span className="ti-reload" aria-hidden="true" /> Nouvelle génération
            </button>
          </div>
        </section>
      )}
    </div>
  );
}
