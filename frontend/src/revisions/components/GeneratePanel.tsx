import { useRef, useState } from "react";
import type { FormEvent } from "react";
import { api } from "../../api/client";
import { Alert, Modal } from "../../components/UI";
import type { AIJob, Sheet } from "../types";
import { summaryLengths } from "../types";
import { useAIStatus } from "./AIStudio";
export default function GeneratePanel({
  sheet,
  onClose,
  onStarted,
}: {
  sheet: Sheet;
  onClose: () => void;
  onStarted: (job: AIJob) => void;
}) {
  const status = useAIStatus();
  const [mode, setMode] = useState<"text" | "file">("text"),
    [text, setText] = useState(""),
    [file, setFile] = useState<File | null>(null),
    [length, setLength] = useState<keyof typeof summaryLengths>("STANDARD"),
    [busy, setBusy] = useState(false),
    [error, setError] = useState<unknown>(),
    [dragging, setDragging] = useState(false);
  const fileInput = useRef<HTMLInputElement>(null);
  const hasContent = !!(sheet.summary.trim() || sheet.key_points.length);
  async function submit(e: FormEvent) {
    e.preventDefault();
    if (busy) return;
    setError(undefined);
    let body: FormData | Record<string, string>;
    if (mode === "file") {
      if (!file)
        return setError(
          new Error("Choisissez un fichier PDF, TXT ou Markdown."),
        );
      body = new FormData();
      body.append("file", file);
      body.append("length", length);
    } else {
      if (text.trim().length < 80)
        return setError(
          new Error(
            "Collez au moins quelques paragraphes du cours (80 caractères minimum).",
          ),
        );
      body = { source_text: text, length };
    }
    setBusy(true);
    try {
      // The server answers at once (202): the generation continues in the background.
      onStarted(
        await api<AIJob>("sheets/" + sheet.id + "/generate/", "POST", body),
      );
    } catch (err) {
      setError(err);
      setBusy(false);
    }
  }
  function pick(files: FileList | null) {
    const chosen = files?.[0];
    if (!chosen) return;
    if (!/\.(pdf|txt|md)$/i.test(chosen.name))
      return setError(new Error("Formats acceptés : PDF, TXT ou Markdown."));
    if (chosen.size > 10 * 1024 * 1024)
      return setError(new Error("La taille maximale est de 10 Mo."));
    setError(undefined);
    setFile(chosen);
  }
  return (
    <Modal
      title="Résumer un cours avec l’IA"
      onClose={() => !busy && onClose()}
    >
      <div className="sheets-module sheets-dialog">
        <form onSubmit={submit} noValidate>
          <p className="intro">
            L’IA rédige un résumé structuré, des points clés, un glossaire et
            une idée d’illustration à partir de votre cours. Vous relirez tout
            avant de partager la fiche.
          </p>
          {status && (
            <p className="sheets-hint">
              <span className="ti-bolt" aria-hidden="true" />
              {status.summary_engine}
              {status.fallback_engine &&
                " · secours " + status.fallback_engine}{" "}
              · traitement en arrière-plan ({status.job_backend})
            </p>
          )}
          <div
            className="sheets-segmented"
            role="group"
            aria-label="Source du cours"
          >
            <button
              type="button"
              aria-pressed={mode === "text"}
              onClick={() => setMode("text")}
            >
              <span className="ti-text" aria-hidden="true" /> Coller le texte
            </button>
            <button
              type="button"
              aria-pressed={mode === "file"}
              onClick={() => setMode("file")}
            >
              <span className="ti-import" aria-hidden="true" /> Importer un
              fichier
            </button>
          </div>
          {mode === "text" ? (
            <div className="field">
              <label htmlFor="ai-source">Contenu du cours</label>
              <textarea
                id="ai-source"
                className="form-control"
                rows={9}
                maxLength={60000}
                value={text}
                onChange={(e) => setText(e.target.value)}
                placeholder="Collez ici le chapitre, vos notes de cours ou la transcription…"
                aria-describedby="ai-source-count"
              />
              <p id="ai-source-count" className="field-help sheets-counter">
                {text.length.toLocaleString("fr-FR")} / 60 000 caractères
              </p>
            </div>
          ) : (
            <div
              className={"sheets-dropzone" + (dragging ? " is-dragging" : "")}
              onDragOver={(e) => {
                e.preventDefault();
                setDragging(true);
              }}
              onDragLeave={() => setDragging(false)}
              onDrop={(e) => {
                e.preventDefault();
                setDragging(false);
                pick(e.dataTransfer.files);
              }}
            >
              <span className="ti-cloud-up" aria-hidden="true" />
              <p>
                {file ? (
                  <strong>{file.name}</strong>
                ) : (
                  "Glissez votre support ici"
                )}
              </p>
              <small>PDF texte, TXT ou Markdown · 10 Mo maximum</small>
              <button
                type="button"
                className="sheets-ghost-button"
                onClick={() => fileInput.current?.click()}
              >
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
          <fieldset className="sheets-choice-grid">
            <legend>Niveau de détail</legend>
            <div className="sheets-choice-options">
              {Object.entries(summaryLengths).map(([key, [label, help]]) => (
                <label
                  key={key}
                  className={length === key ? "is-selected" : ""}
                >
                  <input
                    type="radio"
                    name="length"
                    value={key}
                    checked={length === key}
                    onChange={() =>
                      setLength(key as keyof typeof summaryLengths)
                    }
                  />
                  <strong>{label}</strong>
                  <small>{help}</small>
                </label>
              ))}
            </div>
          </fieldset>
          {hasContent && (
            <p className="notice sheets-warning">
              <span className="ti-alert" aria-hidden="true" /> Le résumé, les
              points clés et le glossaire actuels seront remplacés. Les
              illustrations et étiquettes sont conservées.
            </p>
          )}
          <Alert error={error} />
          <div className="sheets-dialog-actions">
            <button className="btn_one" type="submit" disabled={busy}>
              <span className="ti-wand" aria-hidden="true" />{" "}
              {busy ? "Envoi du cours…" : "Lancer la génération"}
            </button>
            <button
              type="button"
              className="text-button"
              onClick={onClose}
              disabled={busy}
            >
              Annuler
            </button>
          </div>
        </form>
      </div>
    </Modal>
  );
}
