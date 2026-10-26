import { useEffect, useMemo, useRef, useState } from "react";
import type { FormEvent, KeyboardEvent } from "react";
import {
  Link,
  useNavigate,
  useParams,
  useSearchParams,
} from "react-router-dom";
import { allPages, api, ApiError } from "../../api/client";
import type { Group, User } from "../../api/types";
import { Alert, Field, Loading, Select } from "../../components/UI";
import UnsavedChanges from "../../quizzes/UnsavedChanges";
import type { Facets, GlossaryEntry, Sheet, SheetColor } from "../types";
import { sheetColors } from "../types";
import Markdown from "../components/Markdown";
import { useSheetContext } from "../hooks/useSheetContext";
import "../styles/revisions.css";
interface Draft {
  title: string;
  course_label: string;
  learning_group_id: string;
  teacher_id: string;
  color: SheetColor;
  tags: string[];
  summary: string;
  key_points: string[];
  glossary: GlossaryEntry[];
  ai_reviewed: boolean;
}
const blank: Draft = {
  title: "",
  course_label: "",
  learning_group_id: "",
  teacher_id: "",
  color: "INDIGO",
  tags: [],
  summary: "",
  key_points: [],
  glossary: [],
  ai_reviewed: false,
};
const fieldError = (error: unknown, name: string) => {
  if (!(error instanceof ApiError)) return undefined;
  const value = error.fields[name];
  if (!value) return undefined;
  return Array.isArray(value)
    ? value
        .map((v) => (typeof v === "string" ? v : JSON.stringify(v)))
        .join(" ")
    : String(value);
};
export default function SheetEditor() {
  const { id } = useParams(),
    [params] = useSearchParams(),
    navigate = useNavigate();
  const { base, admin, student } = useSheetContext();
  const withAi = !id && params.get("ia") === "1";
  const [draft, setDraft] = useState<Draft>(blank),
    [initial, setInitial] = useState<Draft>(blank),
    [sheet, setSheet] = useState<Sheet | null>(null),
    [groups, setGroups] = useState<Group[]>([]),
    [teachers, setTeachers] = useState<User[]>([]),
    [courses, setCourses] = useState<string[]>([]),
    [loading, setLoading] = useState(!!id),
    [loadError, setLoadError] = useState<unknown>(),
    [error, setError] = useState<unknown>(),
    [busy, setBusy] = useState(false),
    [tagInput, setTagInput] = useState(""),
    [preview, setPreview] = useState(false);
  const leaving = useRef(false);
  useEffect(() => {
    api<Facets>("sheets/facets/")
      .then((f) => setCourses(f.courses))
      .catch(() => undefined);
    if (!student)
      allPages<Group>("groups/").then(setGroups).catch(setLoadError);
    if (admin)
      allPages<User>("admin/users/?role=TEACHER")
        .then(setTeachers)
        .catch(setLoadError);
  }, [admin, student]);
  useEffect(() => {
    if (!id) return;
    api<Sheet>("sheets/" + id + "/")
      .then((s) => {
        const values: Draft = {
          title: s.title,
          course_label: s.course_label,
          learning_group_id: s.learning_group_id || "",
          teacher_id: s.owner_id,
          color: s.color,
          tags: s.tags,
          summary: s.summary,
          key_points: s.key_points,
          glossary: s.glossary,
          ai_reviewed: s.ai_reviewed,
        };
        setSheet(s);
        setDraft(values);
        setInitial(values);
      })
      .catch(setLoadError)
      .finally(() => setLoading(false));
  }, [id]);
  const dirty = useMemo(
    () => JSON.stringify(draft) !== JSON.stringify(initial),
    [draft, initial],
  );
  const set = <K extends keyof Draft>(key: K, value: Draft[K]) =>
    setDraft((d) => ({ ...d, [key]: value }));
  const availableGroups = groups.filter(
    (g) =>
      (!g.archived || g.id === draft.learning_group_id) &&
      (!admin || !draft.teacher_id || g.teacher_id === draft.teacher_id),
  );
  function addTag() {
    const tag = tagInput.trim().replace(/^#/, "").toLowerCase();
    if (tag && !draft.tags.includes(tag) && draft.tags.length < 8)
      set("tags", [...draft.tags, tag.slice(0, 30)]);
    setTagInput("");
  }
  function tagKey(e: KeyboardEvent<HTMLInputElement>) {
    if (e.key === "Enter" || e.key === ",") {
      e.preventDefault();
      addTag();
    } else if (e.key === "Backspace" && !tagInput && draft.tags.length)
      set("tags", draft.tags.slice(0, -1));
  }
  function moveItem<T>(list: T[], index: number, delta: number) {
    const copy = [...list];
    [copy[index], copy[index + delta]] = [copy[index + delta], copy[index]];
    return copy;
  }
  async function submit(e: FormEvent) {
    e.preventDefault();
    if (busy) return;
    setError(undefined);
    const body: Record<string, unknown> = {
      title: draft.title,
      course_label: draft.course_label,
      color: draft.color,
      tags: draft.tags,
      summary: draft.summary,
      key_points: draft.key_points.filter((p) => p.trim()),
      glossary: draft.glossary.filter(
        (g) => g.term.trim() || g.definition.trim(),
      ),
    };
    if (!student && !sheet?.personal)
      body.learning_group_id = draft.learning_group_id;
    if (admin && !sheet?.personal) body.teacher_id = draft.teacher_id;
    if (sheet?.ai_generated) body.ai_reviewed = draft.ai_reviewed;
    if (withAi) {
      delete body.summary;
      delete body.key_points;
      delete body.glossary;
    }
    setBusy(true);
    try {
      const saved = await api<Sheet>(
        id ? "sheets/" + id + "/" : "sheets/",
        id ? "PATCH" : "POST",
        body,
      );
      leaving.current = true;
      navigate(base + "/" + saved.id + (withAi ? "?generer=1" : ""), {
        replace: !!id,
      });
    } catch (err) {
      setError(err);
      window.scrollTo({ top: 0, behavior: "smooth" });
    } finally {
      setBusy(false);
    }
  }
  if (loading) return <Loading />;
  if (loadError && id)
    return (
      <div className="sheets-module">
        <Alert error={loadError} />
        <Link className="text-button" to={base}>
          ← Retour aux fiches
        </Link>
      </div>
    );
  if (sheet && (!sheet.can_edit || sheet.status === "ARCHIVED"))
    return (
      <div className="sheets-module">
        <Alert error="Cette fiche ne peut pas être modifiée." />
        <Link className="text-button" to={base + "/" + sheet.id}>
          ← Retour à la fiche
        </Link>
      </div>
    );
  return (
    <div className="sheets-module sheet-editor" data-color={draft.color}>
      <UnsavedChanges dirty={dirty} ignore={leaving} />
      <nav className="sheet-back" aria-label="Retour">
        <Link to={id ? base + "/" + id : base}>
          <span className="ti-arrow-left" aria-hidden="true" />{" "}
          {id ? "Retour à la fiche" : "Toutes les fiches"}
        </Link>
      </nav>
      <div className="page-heading">
        <div>
          <p className="eyebrow">
            {id
              ? "MODIFIER LA FICHE"
              : withAi
                ? "NOUVELLE FICHE · GEMINI"
                : "NOUVELLE FICHE"}
          </p>
          <h1>
            {id
              ? draft.title || "Fiche sans titre"
              : "Créer une fiche de révision"}
          </h1>
          <p>
            {withAi
              ? "Étape 1 sur 2 : décrivez la fiche. À l’étape suivante, collez votre cours ou importez un PDF et Gemini rédigera le contenu."
              : "Les champs marqués d’un astérisque sont obligatoires. Le contenu reste modifiable à tout moment."}
          </p>
        </div>
      </div>
      {withAi && (
        <ol className="sheet-steps" aria-label="Étapes">
          <li className="current">
            <span>1</span> Informations
          </li>
          <li>
            <span>2</span> Génération avec Gemini
          </li>
          <li>
            <span>3</span> Relecture et partage
          </li>
        </ol>
      )}
      <form onSubmit={submit} noValidate className="sheet-form">
        <Alert error={error || loadError} />
        <section className="sheet-form-card">
          <h2>
            <span className="ti-id-badge" aria-hidden="true" /> Identité de la
            fiche
          </h2>
          <div className="form-grid">
            <Field
              label="Titre *"
              required
              maxLength={120}
              value={draft.title}
              onChange={(e) => set("title", e.target.value)}
              error={fieldError(error, "title")}
              placeholder="Ex. : La photosynthèse"
            />
            <div className="field">
              <label htmlFor="course-label">Cours ou matière *</label>
              <input
                id="course-label"
                className="form-control"
                list="course-options"
                required
                maxLength={120}
                value={draft.course_label}
                onChange={(e) => set("course_label", e.target.value)}
                aria-invalid={
                  fieldError(error, "course_label") ? true : undefined
                }
                aria-describedby={
                  fieldError(error, "course_label") ? "course-error" : undefined
                }
                placeholder="Ex. : Biologie végétale"
              />
              <datalist id="course-options">
                {courses.map((c) => (
                  <option key={c} value={c} />
                ))}
              </datalist>
              {fieldError(error, "course_label") && (
                <p id="course-error" className="field-help notice-error">
                  {fieldError(error, "course_label")}
                </p>
              )}
            </div>
            {admin && !sheet?.personal && (
              <Select
                label="Enseignant propriétaire *"
                required
                value={draft.teacher_id}
                disabled={sheet?.status === "PUBLISHED"}
                onChange={(e) =>
                  setDraft((d) => ({
                    ...d,
                    teacher_id: e.target.value,
                    learning_group_id: "",
                  }))
                }
                error={fieldError(error, "teacher_id")}
              >
                <option value="">Sélectionnez un enseignant</option>
                {teachers.map((t) => (
                  <option key={t.id} value={t.id}>
                    {t.first_name} {t.last_name}
                  </option>
                ))}
              </Select>
            )}
            {!student && !sheet?.personal && (
              <Select
                label="Groupe destinataire *"
                required
                value={draft.learning_group_id}
                disabled={sheet?.status === "PUBLISHED"}
                onChange={(e) => set("learning_group_id", e.target.value)}
                error={fieldError(error, "learning_group_id")}
              >
                <option value="">Sélectionnez un groupe</option>
                {availableGroups.map((g) => (
                  <option key={g.id} value={g.id}>
                    {g.name} ({g.code})
                  </option>
                ))}
              </Select>
            )}
          </div>
          {sheet?.status === "PUBLISHED" && !student && (
            <p className="field-help">
              Le groupe d’une fiche publiée ne peut pas changer. Repassez-la en
              brouillon pour le modifier.
            </p>
          )}
          {student && (
            <p className="field-help">
              <span className="ti-lock" aria-hidden="true" /> Vos fiches
              personnelles ne sont visibles que par vous.
            </p>
          )}
          <fieldset className="sheet-colors">
            <legend>Couleur de la fiche</legend>
            {(Object.keys(sheetColors) as SheetColor[]).map((color) => (
              <label key={color} data-color={color} title={sheetColors[color]}>
                <input
                  type="radio"
                  name="color"
                  value={color}
                  checked={draft.color === color}
                  onChange={() => set("color", color)}
                />
                <span className="swatch" aria-hidden="true" />
                <span className="sr-only">{sheetColors[color]}</span>
              </label>
            ))}
          </fieldset>
          <div className="field">
            <label htmlFor="tag-input">
              Étiquettes ({draft.tags.length}/8)
            </label>
            <div className="sheet-tag-input">
              {draft.tags.map((tag) => (
                <span key={tag} className="sheet-chip tag">
                  #{tag}
                  <button
                    type="button"
                    aria-label={"Retirer l’étiquette " + tag}
                    onClick={() =>
                      set(
                        "tags",
                        draft.tags.filter((t) => t !== tag),
                      )
                    }
                  >
                    ×
                  </button>
                </span>
              ))}
              <input
                id="tag-input"
                value={tagInput}
                maxLength={30}
                disabled={draft.tags.length >= 8}
                onChange={(e) => setTagInput(e.target.value)}
                onKeyDown={tagKey}
                onBlur={addTag}
                placeholder={draft.tags.length ? "" : "révision, chapitre-3…"}
                aria-describedby="tag-help"
              />
            </div>
            <p id="tag-help" className="field-help">
              Appuyez sur Entrée ou virgule pour ajouter une étiquette.
            </p>
            {fieldError(error, "tags") && (
              <p className="field-help notice-error">
                {fieldError(error, "tags")}
              </p>
            )}
          </div>
        </section>
        {withAi ? (
          <section className="sheet-form-card sheet-ai-intro">
            <div className="ai-orb" aria-hidden="true">
              <span className="ti-wand" />
            </div>
            <div>
              <h2>Gemini prendra le relais</h2>
              <p>
                Après l’enregistrement, vous collerez votre cours ou importerez
                un PDF. Gemini rédigera un résumé structuré, les points clés, un
                glossaire et une idée d’illustration. Vous relirez tout avant le
                partage.
              </p>
            </div>
          </section>
        ) : (
          <>
            <section className="sheet-form-card">
              <div className="sheet-form-card-heading">
                <h2>
                  <span className="ti-book" aria-hidden="true" /> Résumé
                </h2>
                <div
                  className="sheets-segmented small"
                  role="group"
                  aria-label="Mode d’affichage du résumé"
                >
                  <button
                    type="button"
                    aria-pressed={!preview}
                    onClick={() => setPreview(false)}
                  >
                    Rédiger
                  </button>
                  <button
                    type="button"
                    aria-pressed={preview}
                    onClick={() => setPreview(true)}
                  >
                    Aperçu
                  </button>
                </div>
              </div>
              {preview ? (
                <div className="sheet-preview-box">
                  {draft.summary.trim() ? (
                    <Markdown text={draft.summary} />
                  ) : (
                    <p className="field-help">
                      Rien à afficher pour l’instant.
                    </p>
                  )}
                </div>
              ) : (
                <div className="field">
                  <label htmlFor="summary">Texte du résumé</label>
                  <textarea
                    id="summary"
                    className="form-control sheet-summary-input"
                    rows={14}
                    maxLength={20000}
                    value={draft.summary}
                    onChange={(e) => set("summary", e.target.value)}
                    aria-describedby="summary-help"
                    aria-invalid={
                      fieldError(error, "summary") ? true : undefined
                    }
                  />
                  <p id="summary-help" className="field-help sheets-counter">
                    Mise en forme : <code>## Titre</code>, <code>- liste</code>,{" "}
                    <code>**gras**</code> ·{" "}
                    {draft.summary.length.toLocaleString("fr-FR")} / 20 000
                  </p>
                  {fieldError(error, "summary") && (
                    <p className="field-help notice-error">
                      {fieldError(error, "summary")}
                    </p>
                  )}
                </div>
              )}
            </section>
            <section className="sheet-form-card">
              <div className="sheet-form-card-heading">
                <h2>
                  <span className="ti-star" aria-hidden="true" /> Points clés
                  <small>{draft.key_points.length}/15</small>
                </h2>
                <button
                  type="button"
                  className="sheets-ghost-button"
                  disabled={draft.key_points.length >= 15}
                  onClick={() => set("key_points", [...draft.key_points, ""])}
                >
                  <span className="ti-plus" aria-hidden="true" /> Ajouter un
                  point
                </button>
              </div>
              {fieldError(error, "key_points") && (
                <p className="field-help notice-error">
                  {fieldError(error, "key_points")}
                </p>
              )}
              {draft.key_points.length ? (
                <ol className="sheet-list-editor">
                  {draft.key_points.map((point, i) => (
                    <li key={i}>
                      <span className="sheet-list-index" aria-hidden="true">
                        {i + 1}
                      </span>
                      <label className="sr-only" htmlFor={"point-" + i}>
                        Point clé {i + 1}
                      </label>
                      <input
                        id={"point-" + i}
                        className="form-control"
                        maxLength={300}
                        value={point}
                        onChange={(e) =>
                          set(
                            "key_points",
                            draft.key_points.map((p, j) =>
                              j === i ? e.target.value : p,
                            ),
                          )
                        }
                      />
                      <div className="sheet-row-tools">
                        <button
                          type="button"
                          disabled={i === 0}
                          aria-label={"Monter le point " + (i + 1)}
                          onClick={() =>
                            set("key_points", moveItem(draft.key_points, i, -1))
                          }
                        >
                          <span className="ti-arrow-up" aria-hidden="true" />
                        </button>
                        <button
                          type="button"
                          disabled={i === draft.key_points.length - 1}
                          aria-label={"Descendre le point " + (i + 1)}
                          onClick={() =>
                            set("key_points", moveItem(draft.key_points, i, 1))
                          }
                        >
                          <span className="ti-arrow-down" aria-hidden="true" />
                        </button>
                        <button
                          type="button"
                          className="danger"
                          aria-label={"Supprimer le point " + (i + 1)}
                          onClick={() =>
                            set(
                              "key_points",
                              draft.key_points.filter((_, j) => j !== i),
                            )
                          }
                        >
                          <span className="ti-trash" aria-hidden="true" />
                        </button>
                      </div>
                    </li>
                  ))}
                </ol>
              ) : (
                <p className="field-help">
                  Les points clés résument ce qu’il faut absolument retenir. Une
                  fiche publiée en contient au moins un.
                </p>
              )}
            </section>
            <section className="sheet-form-card">
              <div className="sheet-form-card-heading">
                <h2>
                  <span className="ti-bookmark-alt" aria-hidden="true" />{" "}
                  Glossaire
                  <small>{draft.glossary.length}/20</small>
                </h2>
                <button
                  type="button"
                  className="sheets-ghost-button"
                  disabled={draft.glossary.length >= 20}
                  onClick={() =>
                    set("glossary", [
                      ...draft.glossary,
                      { term: "", definition: "" },
                    ])
                  }
                >
                  <span className="ti-plus" aria-hidden="true" /> Ajouter une
                  définition
                </button>
              </div>
              {fieldError(error, "glossary") && (
                <p className="field-help notice-error">
                  {fieldError(error, "glossary")}
                </p>
              )}
              {draft.glossary.length ? (
                <div className="sheet-glossary-editor">
                  {draft.glossary.map((entry, i) => (
                    <div key={i} className="sheet-glossary-row">
                      <Field
                        label={"Terme " + (i + 1)}
                        maxLength={80}
                        value={entry.term}
                        onChange={(e) =>
                          set(
                            "glossary",
                            draft.glossary.map((g, j) =>
                              j === i ? { ...g, term: e.target.value } : g,
                            ),
                          )
                        }
                      />
                      <Field
                        label="Définition"
                        maxLength={400}
                        value={entry.definition}
                        onChange={(e) =>
                          set(
                            "glossary",
                            draft.glossary.map((g, j) =>
                              j === i
                                ? { ...g, definition: e.target.value }
                                : g,
                            ),
                          )
                        }
                      />
                      <button
                        type="button"
                        className="sheet-row-remove"
                        aria-label={"Supprimer la définition " + (i + 1)}
                        onClick={() =>
                          set(
                            "glossary",
                            draft.glossary.filter((_, j) => j !== i),
                          )
                        }
                      >
                        <span className="ti-trash" aria-hidden="true" />
                      </button>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="field-help">
                  Définissez les notions essentielles du cours.
                </p>
              )}
            </section>
            {sheet?.ai_generated && (
              <section className="sheet-form-card sheet-review-check">
                <label>
                  <input
                    type="checkbox"
                    checked={draft.ai_reviewed}
                    onChange={(e) => set("ai_reviewed", e.target.checked)}
                  />
                  <span>
                    <strong>J’ai relu le contenu généré par l’IA.</strong> Je
                    confirme son exactitude
                    {student ? "." : " avant de le partager avec mon groupe."}
                  </span>
                </label>
              </section>
            )}
          </>
        )}
        <div className="sheet-form-actions">
          <button className="btn_one" disabled={busy}>
            {busy ? (
              "Enregistrement…"
            ) : withAi ? (
              <>
                Continuer vers Gemini <span aria-hidden="true">→</span>
              </>
            ) : id ? (
              "Enregistrer les modifications"
            ) : (
              "Créer la fiche"
            )}
          </button>
          <Link className="text-button" to={id ? base + "/" + id : base}>
            Annuler
          </Link>
        </div>
      </form>
    </div>
  );
}
