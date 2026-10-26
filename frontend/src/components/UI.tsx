import { t } from "../quizzes/i18n";
import { useEffect, useId, useRef, useState } from "react";
import type {
  ReactNode,
  FormEvent,
  InputHTMLAttributes,
  SelectHTMLAttributes,
  TextareaHTMLAttributes,
  FocusEventHandler,
  Ref,
} from "react";
import { ApiError } from "../api/client";
export function Alert({
  error,
  success,
}: {
  error?: unknown;
  success?: string;
}) {
  if (!error && !success) return null;
  return (
    <div
      className={"notice " + (error ? "notice-error" : "")}
      role={error ? "alert" : "status"}
    >
      {error instanceof ApiError ? (
        <>
          {t(error.message)}
          {Object.entries(error.fields).map(([k, v]) => (
            <p key={k}>
              {t(labels[k] || k)} :{" "}
              {Array.isArray(v) ? v.map((item) => t(item)).join(" ") : t(v)}
            </p>
          ))}
        </>
      ) : error instanceof Error ? (
        t(error.message)
      ) : (
        t(String(error || success))
      )}
    </div>
  );
}
const labels: Record<string, string> = {
  rating: "Appréciation",
  comment: "Commentaire",
  opens_at: "Ouverture",
  closes_at: "Fermeture",
  title: "Titre",
  learning_group_id: "Groupe pédagogique",
  statement: "Énoncé",
  choice_a: "Proposition A",
  choice_b: "Proposition B",
  choice_c: "Proposition C",
  choice_d: "Proposition D",
  correct_answer: "Bonne réponse",
  points: "Points",
  position: "Position",
  publication: "Publication",
  duration_minutes: "Durée",
  max_attempts: "Tentatives",
  explanation: "Explication",
  description: "Description",
  question_ids: "Ordre des questions",
  level: "Niveau",
  email: "Email",
  password: "Mot de passe",
  confirmation: "Confirmation",
  role: "Rôle",
  teacher_id: "Enseignant",
  duration_mode: "Durée du quiz",
  ends_at: "Fin",
  reason: "Motif",
  first_name: "Prénom",
  last_name: "Nom",
  old_password: "Ancien mot de passe",
  non_field_errors: "Validation",
};
export function Field({
  label,
  error,
  ...props
}: InputHTMLAttributes<HTMLInputElement> & { label: string; error?: string }) {
  const id = useId();
  return (
    <div className="field">
      <label htmlFor={id}>{t(label)}</label>
      <input
        id={id}
        className="form-control"
        {...props}
        aria-invalid={error ? true : undefined}
        aria-describedby={error ? id + "-error" : props["aria-describedby"]}
      />
      {error && (
        <p id={id + "-error"} className="field-help notice-error">
          {t(error)}
        </p>
      )}
    </div>
  );
}
export function Select({
  label,
  error,
  children,
  ...props
}: SelectHTMLAttributes<HTMLSelectElement> & {
  label: string;
  error?: string;
  children: ReactNode;
}) {
  const id = useId();
  return (
    <div className="field">
      <label htmlFor={id}>{t(label)}</label>
      <select
        id={id}
        className="form-control"
        {...props}
        aria-invalid={error ? true : undefined}
        aria-describedby={error ? id + "-error" : props["aria-describedby"]}
      >
        {children}
      </select>
      {error && (
        <p id={id + "-error"} className="field-help notice-error">
          {t(error)}
        </p>
      )}
    </div>
  );
}
export function Empty({
  children = t("Aucune donnée à afficher pour le moment."),
  title = t("Tout commence ici"),
  headingLevel = 3,
}: {
  children?: ReactNode;
  title?: string;
  headingLevel?: 2 | 3;
}) {
  const Heading = headingLevel === 2 ? "h2" : "h3";
  return (
    <div className="empty">
      <span className="ti-folder" aria-hidden="true" />
      <Heading>{t(title)}</Heading>
      <p>{children}</p>
    </div>
  );
}
export function Loading() {
  return (
    <p className="loading" role="status">
      {t("Chargement en cours… ")}
    </p>
  );
}
export function Badge({ children }: { children: ReactNode }) {
  return (
    <span className="status-badge">
      {typeof children === "string" ? t(children) : children}
    </span>
  );
}
export function Pagination({
  page,
  count,
  onChange,
}: {
  page: number;
  count: number;
  onChange: (p: number) => void;
}) {
  return count > 20 ? (
    <nav aria-label={t("Pagination")} className="pagination-hub">
      <button disabled={page <= 1} onClick={() => onChange(page - 1)}>
        {t("Précédent ")}
      </button>
      <span>
        {t("Page ")}
        {page}
        {t(" sur ")}
        {Math.ceil(count / 20)}
      </span>
      <button disabled={page * 20 >= count} onClick={() => onChange(page + 1)}>
        {t("Suivant ")}
      </button>
    </nav>
  ) : null;
}
export function Modal({
  title,
  children,
  onClose,
}: {
  title: string;
  children: ReactNode;
  onClose: () => void;
}) {
  const ref = useRef<HTMLDialogElement>(null),
    id = useId();
  useEffect(() => {
    const previous = document.activeElement as HTMLElement;
    const dialog = ref.current;
    dialog?.showModal();
    return () => {
      dialog?.close();
      if (previous?.isConnected) previous.focus();
    };
  }, []);
  return (
    <dialog ref={ref} aria-labelledby={id} onCancel={onClose}>
      <div className="modal-title">
        <h2 id={id}>{t(title)}</h2>
        <button
          className="icon-button"
          onClick={onClose}
          aria-label={t("Fermer")}
        >
          ×
        </button>
      </div>
      {children}
    </dialog>
  );
}
export function Form({
  onSubmit,
  children,
  label = t("Enregistrer"),
  onSuccess,
  noValidate = false,
  onBlur,
  formRef,
  clearErrorOnChange = false,
}: {
  onSubmit: (form: FormData) => Promise<unknown>;
  children?: ReactNode;
  label?: string;
  onSuccess?: () => void;
  noValidate?: boolean;
  onBlur?: FocusEventHandler<HTMLFormElement>;
  formRef?: Ref<HTMLFormElement>;
  clearErrorOnChange?: boolean;
}) {
  const [busy, setBusy] = useState(false),
    [error, setError] = useState<unknown>(),
    [success, setSuccess] = useState("");
  const locked = useRef(false);
  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (locked.current) return;
    locked.current = true;
    setBusy(true);
    setError(undefined);
    setSuccess("");
    const form = new FormData(e.currentTarget);
    try {
      await onSubmit(form);
      setSuccess(t("Enregistrement effectué."));
      onSuccess?.();
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
      locked.current = false;
    }
  }
  return (
    <form
      onSubmit={submit}
      noValidate={noValidate}
      onBlur={onBlur}
      ref={formRef}
      onChange={
        clearErrorOnChange
          ? () => {
              setError(undefined);
              setSuccess("");
            }
          : undefined
      }
    >
      <Alert error={error} success={success} />
      {children}
      <button className="btn_one" disabled={busy}>
        {busy ? t("Veuillez patienter…") : t(label)}
      </button>
    </form>
  );
}
export const val = (form: FormData, name: string) =>
  String(form.get(name) || "");
export const statuses: Record<string, string> = {
  UNSET: "Non renseigné",
  PRESENT: "Présent",
  LATE: "En retard",
  ABSENT: "Absent",
  EXCUSED: "Absence justifiée",
  PLANNED: "Planifiée",
  COMPLETED: "Terminée",
  CANCELLED: "Annulée",
  STUDENT: "Étudiant",
  TEACHER: "Enseignant",
  ADMIN: "Administrateur",
};

export function Textarea({
  label,
  error,
  ...props
}: TextareaHTMLAttributes<HTMLTextAreaElement> & {
  label: string;
  error?: string;
}) {
  const id = useId();
  return (
    <div className="field">
      <label htmlFor={id}>{t(label)}</label>
      <textarea
        id={id}
        className="form-control"
        {...props}
        aria-invalid={error ? true : undefined}
        aria-describedby={error ? id + "-error" : props["aria-describedby"]}
      />
      {error && (
        <p id={id + "-error"} className="field-help notice-error">
          {t(error)}
        </p>
      )}
    </div>
  );
}
