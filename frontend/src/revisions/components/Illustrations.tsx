import { useEffect, useRef, useState } from "react";
import type { FormEvent } from "react";
import { api } from "../../api/client";
import { Alert, Modal, Textarea } from "../../components/UI";
import type { AIJob, Illustration, Sheet } from "../types";
import { useAIStatus } from "./AIStudio";
import { illustrationStyles } from "../types";
function UploadDialog({
  sheet,
  onClose,
  onAdded,
}: {
  sheet: Sheet;
  onClose: () => void;
  onAdded: (ill: Illustration) => void;
}) {
  const [file, setFile] = useState<File | null>(null),
    [preview, setPreview] = useState(""),
    [caption, setCaption] = useState(""),
    [busy, setBusy] = useState(false),
    [error, setError] = useState<unknown>();
  const input = useRef<HTMLInputElement>(null);
  useEffect(() => {
    if (!file) return;
    const url = URL.createObjectURL(file);
    setPreview(url);
    return () => URL.revokeObjectURL(url);
  }, [file]);
  function pick(files: FileList | null) {
    const chosen = files?.[0];
    if (!chosen) return;
    if (!/^image\/(png|jpeg|webp)$/.test(chosen.type))
      return setError(new Error("Formats acceptés : PNG, JPEG ou WebP."));
    if (chosen.size > 8 * 1024 * 1024)
      return setError(new Error("La taille maximale est de 8 Mo."));
    setError(undefined);
    setFile(chosen);
  }
  async function submit(e: FormEvent) {
    e.preventDefault();
    if (!file) return setError(new Error("Choisissez une image."));
    if (!caption.trim())
      return setError(
        new Error("Décrivez l’image pour les personnes qui ne la voient pas."),
      );
    const body = new FormData();
    body.append("image", file);
    body.append("caption", caption.trim());
    setBusy(true);
    setError(undefined);
    try {
      onAdded(
        await api<Illustration>(
          "sheets/" + sheet.id + "/illustrations/",
          "POST",
          body,
        ),
      );
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  }
  return (
    <Modal title="Importer une illustration" onClose={() => !busy && onClose()}>
      <form
        className="sheets-module sheets-dialog"
        onSubmit={submit}
        noValidate
      >
        <div
          className="sheets-dropzone"
          onDragOver={(e) => e.preventDefault()}
          onDrop={(e) => {
            e.preventDefault();
            pick(e.dataTransfer.files);
          }}
        >
          {preview ? (
            <img className="sheets-upload-preview" src={preview} alt="" />
          ) : (
            <span className="ti-image" aria-hidden="true" />
          )}
          <p>{file ? <strong>{file.name}</strong> : "Glissez une image ici"}</p>
          <small>
            PNG, JPEG ou WebP · 8 Mo maximum · optimisée automatiquement
          </small>
          <button
            type="button"
            className="sheets-ghost-button"
            onClick={() => input.current?.click()}
          >
            {file ? "Changer d’image" : "Parcourir mes fichiers"}
          </button>
          <input
            ref={input}
            type="file"
            hidden
            accept="image/png,image/jpeg,image/webp"
            onChange={(e) => pick(e.target.files)}
          />
        </div>
        <Textarea
          label="Description accessible (texte alternatif)"
          rows={2}
          maxLength={300}
          value={caption}
          onChange={(e) => setCaption(e.target.value)}
          placeholder="Ex. : Schéma du cycle de Calvin dans le chloroplaste"
        />
        <Alert error={error} />
        <div className="sheets-dialog-actions">
          <button className="btn_one" disabled={busy}>
            {busy ? "Import en cours…" : "Ajouter à la fiche"}
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
    </Modal>
  );
}
export function IllustrationDialog({
  sheet,
  onClose,
  onStarted,
}: {
  sheet: Sheet;
  onClose: () => void;
  onStarted: (job: AIJob) => void;
}) {
  const status = useAIStatus();
  const [prompt, setPrompt] = useState(sheet.illustration_prompt || ""),
    [caption, setCaption] = useState(""),
    [style, setStyle] = useState<keyof typeof illustrationStyles>("SCHEMA"),
    [busy, setBusy] = useState(false),
    [error, setError] = useState<unknown>();
  async function submit(e: FormEvent) {
    e.preventDefault();
    if (prompt.trim().length < 8)
      return setError(
        new Error("Décrivez l’image souhaitée en une phrase au moins."),
      );
    if (!caption.trim())
      return setError(
        new Error("Ajoutez une description accessible de l’illustration."),
      );
    setBusy(true);
    setError(undefined);
    try {
      // 202: the image is drawn in the background and added to the gallery when ready.
      onStarted(
        await api<AIJob>(
          "sheets/" + sheet.id + "/illustrations/generate/",
          "POST",
          { prompt: prompt.trim(), caption: caption.trim(), style },
        ),
      );
    } catch (err) {
      setError(err);
      setBusy(false);
    }
  }
  return (
    <Modal
      title="Créer une illustration avec l’IA"
      onClose={() => !busy && onClose()}
    >
      <div className="sheets-module sheets-dialog">
        <form onSubmit={submit} noValidate>
          <p className="intro">
            Décrivez l’image (en français ou en anglais). Les meilleurs
            résultats viennent de descriptions concrètes : objets, disposition,
            couleurs.
          </p>
          {sheet.illustration_prompt &&
            prompt === sheet.illustration_prompt && (
              <p className="sheets-hint">
                <span className="ti-light-bulb" aria-hidden="true" /> Idée
                proposée par Gemini lors de la génération du résumé.
              </p>
            )}
          <Textarea
            label="Description de l’image à générer"
            rows={3}
            maxLength={600}
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            placeholder="Ex. : A green leaf absorbing sunlight, arrows showing CO2 and water entering, oxygen leaving"
          />
          <fieldset className="sheets-choice-grid styles">
            <legend>Style visuel</legend>
            <div className="sheets-choice-options">
              {Object.entries(illustrationStyles).map(
                ([key, [label, icon]]) => (
                  <label
                    key={key}
                    className={style === key ? "is-selected" : ""}
                  >
                    <input
                      type="radio"
                      name="style"
                      value={key}
                      checked={style === key}
                      onChange={() =>
                        setStyle(key as keyof typeof illustrationStyles)
                      }
                    />
                    <span className={icon} aria-hidden="true" />
                    <strong>{label}</strong>
                  </label>
                ),
              )}
            </div>
          </fieldset>
          <Textarea
            label="Description accessible (texte alternatif)"
            rows={2}
            maxLength={300}
            value={caption}
            onChange={(e) => setCaption(e.target.value)}
            placeholder="Ce que montre l’image, en français"
          />
          <Alert error={error} />
          <div className="sheets-dialog-actions">
            <button className="btn_one" type="submit" disabled={busy}>
              <span className="ti-wand" aria-hidden="true" />{" "}
              {busy ? "Envoi…" : "Lancer la création"}
            </button>
            <button type="button" className="text-button" onClick={onClose}>
              Annuler
            </button>
          </div>
        </form>
      </div>
    </Modal>
  );
}
function CaptionEditor({
  sheet,
  ill,
  onSaved,
  onCancel,
}: {
  sheet: Sheet;
  ill: Illustration;
  onSaved: (ill: Illustration) => void;
  onCancel: () => void;
}) {
  const [caption, setCaption] = useState(ill.caption),
    [error, setError] = useState<unknown>(),
    [busy, setBusy] = useState(false);
  async function save(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    try {
      onSaved(
        await api<Illustration>(
          "sheets/" + sheet.id + "/illustrations/" + ill.id + "/",
          "PATCH",
          { caption },
        ),
      );
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  }
  return (
    <form className="sheets-caption-form" onSubmit={save}>
      <Textarea
        label="Description"
        rows={2}
        maxLength={300}
        value={caption}
        onChange={(e) => setCaption(e.target.value)}
        autoFocus
      />
      <Alert error={error} />
      <div className="actions">
        <button className="text-button" disabled={busy}>
          Enregistrer
        </button>
        <button type="button" className="text-button" onClick={onCancel}>
          Annuler
        </button>
      </div>
    </form>
  );
}
export default function Illustrations({
  sheet,
  editable,
  pending,
  onChange,
  onGenerate,
}: {
  sheet: Sheet;
  editable: boolean;
  pending: number;
  onChange: (illustrations: Illustration[]) => void;
  onGenerate: () => void;
}) {
  const items = sheet.illustrations;
  const [dialog, setDialog] = useState<"upload" | null>(null),
    [viewing, setViewing] = useState<number | null>(null),
    [editing, setEditing] = useState<string | null>(null),
    [removing, setRemoving] = useState<Illustration | null>(null),
    [error, setError] = useState<unknown>(),
    [busy, setBusy] = useState(false);
  const full = items.length + pending >= 12;
  async function move(index: number, delta: number) {
    const ids = items.map((i) => i.id);
    [ids[index], ids[index + delta]] = [ids[index + delta], ids[index]];
    setBusy(true);
    try {
      const r = await api<{ results: Illustration[] }>(
        "sheets/" + sheet.id + "/illustrations/reorder/",
        "POST",
        { illustration_ids: ids },
      );
      onChange(r.results);
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  }
  async function remove(ill: Illustration) {
    setBusy(true);
    try {
      await api(
        "sheets/" + sheet.id + "/illustrations/" + ill.id + "/",
        "DELETE",
      );
      onChange(items.filter((i) => i.id !== ill.id));
      setRemoving(null);
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  }
  const added = (ill: Illustration) => {
    onChange([...items, ill]);
    setDialog(null);
  };
  return (
    <section className="sheet-section" aria-labelledby="sheet-illustrations">
      <div className="sheet-section-heading">
        <h2 id="sheet-illustrations">
          <span className="ti-gallery" aria-hidden="true" /> Illustrations
          <small>{items.length} / 12</small>
        </h2>
        {editable && (
          <div className="actions no-print">
            <button
              className="sheets-ghost-button"
              disabled={full}
              onClick={() => setDialog("upload")}
            >
              <span className="ti-upload" aria-hidden="true" /> Importer
            </button>
            <button
              className="sheets-ai-button"
              disabled={full}
              onClick={onGenerate}
            >
              <span className="ti-wand" aria-hidden="true" /> Générer avec
              Hugging Face
            </button>
          </div>
        )}
      </div>
      <Alert error={error} />
      {items.length ? (
        <div className="sheet-gallery">
          {items.map((ill, index) => (
            <figure key={ill.id} className="sheet-figure">
              <button
                type="button"
                className="sheet-figure-image"
                onClick={() => setViewing(index)}
                aria-label={"Agrandir : " + ill.caption}
              >
                <img
                  src={ill.url}
                  alt={ill.caption}
                  width={ill.width}
                  height={ill.height}
                  loading="lazy"
                />
                {ill.source === "AI" && (
                  <span className="sheet-figure-badge">
                    <span className="ti-wand" aria-hidden="true" /> IA
                  </span>
                )}
              </button>
              {editing === ill.id ? (
                <CaptionEditor
                  sheet={sheet}
                  ill={ill}
                  onCancel={() => setEditing(null)}
                  onSaved={(saved) => {
                    onChange(items.map((i) => (i.id === saved.id ? saved : i)));
                    setEditing(null);
                  }}
                />
              ) : (
                <figcaption>
                  <strong>Figure {index + 1}.</strong> {ill.caption}
                </figcaption>
              )}
              {editable && editing !== ill.id && (
                <div className="sheet-figure-tools no-print">
                  <button
                    type="button"
                    disabled={busy || index === 0}
                    onClick={() => void move(index, -1)}
                    aria-label={"Avancer la figure " + (index + 1)}
                    title="Déplacer avant"
                  >
                    <span className="ti-arrow-left" aria-hidden="true" />
                  </button>
                  <button
                    type="button"
                    disabled={busy || index === items.length - 1}
                    onClick={() => void move(index, 1)}
                    aria-label={"Reculer la figure " + (index + 1)}
                    title="Déplacer après"
                  >
                    <span className="ti-arrow-right" aria-hidden="true" />
                  </button>
                  <button
                    type="button"
                    onClick={() => setEditing(ill.id)}
                    aria-label={
                      "Modifier la description de la figure " + (index + 1)
                    }
                    title="Modifier la description"
                  >
                    <span className="ti-pencil" aria-hidden="true" />
                  </button>
                  <button
                    type="button"
                    className="danger"
                    onClick={() => setRemoving(ill)}
                    aria-label={"Supprimer la figure " + (index + 1)}
                    title="Supprimer"
                  >
                    <span className="ti-trash" aria-hidden="true" />
                  </button>
                </div>
              )}
            </figure>
          ))}
        </div>
      ) : (
        <div className="sheet-gallery-empty">
          <span className="ti-image" aria-hidden="true" />
          <p>
            {editable
              ? "Ajoutez un schéma, une photo ou laissez un modèle Hugging Face créer une illustration à partir de votre description."
              : "Aucune illustration pour cette fiche."}
          </p>
        </div>
      )}
      {dialog === "upload" && (
        <UploadDialog
          sheet={sheet}
          onClose={() => setDialog(null)}
          onAdded={added}
        />
      )}
      {viewing !== null && items[viewing] && (
        <Modal
          title={"Figure " + (viewing + 1) + " sur " + items.length}
          onClose={() => setViewing(null)}
        >
          <div className="sheet-lightbox">
            <img src={items[viewing].url} alt={items[viewing].caption} />
            <p>{items[viewing].caption}</p>
            {items[viewing].source === "AI" && (
              <p className="field-help">
                Générée avec {items[viewing].ai_model} · «{" "}
                {items[viewing].prompt} »
              </p>
            )}
            {items.length > 1 && (
              <div className="actions">
                <button
                  className="sheets-ghost-button"
                  disabled={viewing === 0}
                  onClick={() => setViewing(viewing - 1)}
                >
                  ← Précédente
                </button>
                <button
                  className="sheets-ghost-button"
                  disabled={viewing === items.length - 1}
                  onClick={() => setViewing(viewing + 1)}
                >
                  Suivante →
                </button>
              </div>
            )}
          </div>
        </Modal>
      )}
      {removing && (
        <Modal
          title="Supprimer cette illustration ?"
          onClose={() => setRemoving(null)}
        >
          <p className="intro">
            L’image « {removing.caption} » sera définitivement supprimée de la
            fiche.
          </p>
          <div className="actions">
            <button
              className="btn_one"
              disabled={busy}
              onClick={() => void remove(removing)}
            >
              Confirmer la suppression
            </button>
            <button className="text-button" onClick={() => setRemoving(null)}>
              Annuler
            </button>
          </div>
        </Modal>
      )}
    </section>
  );
}
