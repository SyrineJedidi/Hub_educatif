import { useEffect, useId, useRef, useState } from "react";
import type {
  ReactNode,
  FormEvent,
  InputHTMLAttributes,
  SelectHTMLAttributes,
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
          {error.message}
          {Object.entries(error.fields).map(([k, v]) => (
            <p key={k}>
              {labels[k] || k} : {Array.isArray(v) ? v.join(" ") : v}
            </p>
          ))}
        </>
      ) : error instanceof Error ? (
        error.message
      ) : (
        String(error || success)
      )}
    </div>
  );
}
const labels: Record<string, string> = {
  email: "Email",
  password: "Mot de passe",
  confirmation: "Confirmation",
  role: "Rôle",
  teacher_id: "Enseignant",
  ends_at: "Fin",
  reason: "Motif",
  first_name: "Prénom",
  last_name: "Nom",
  old_password: "Ancien mot de passe",
  non_field_errors: "Validation",
};
export function Field({
  label,
  ...props
}: InputHTMLAttributes<HTMLInputElement> & { label: string }) {
  const id = useId();
  return (
    <div className="field">
      <label htmlFor={id}>{label}</label>
      <input id={id} className="form-control" {...props} />
    </div>
  );
}
export function Select({
  label,
  children,
  ...props
}: SelectHTMLAttributes<HTMLSelectElement> & {
  label: string;
  children: ReactNode;
}) {
  const id = useId();
  return (
    <div className="field">
      <label htmlFor={id}>{label}</label>
      <select id={id} className="form-control" {...props}>
        {children}
      </select>
    </div>
  );
}
export function Empty({
  children = "Aucune donnée à afficher pour le moment.",
}: {
  children?: ReactNode;
}) {
  return (
    <div className="empty">
      <span className="ti-folder" aria-hidden="true" />
      <h3>Tout commence ici</h3>
      <p>{children}</p>
    </div>
  );
}
export function Loading() {
  return (
    <p className="loading" role="status">
      Chargement en cours…
    </p>
  );
}
export function Badge({ children }: { children: ReactNode }) {
  return <span className="status-badge">{children}</span>;
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
    <nav aria-label="Pagination" className="pagination-hub">
      <button disabled={page <= 1} onClick={() => onChange(page - 1)}>
        Précédent
      </button>
      <span>
        Page {page} sur {Math.ceil(count / 20)}
      </span>
      <button disabled={page * 20 >= count} onClick={() => onChange(page + 1)}>
        Suivant
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
    ref.current?.showModal();
    return () => previous?.focus();
  }, []);
  return (
    <dialog ref={ref} aria-labelledby={id} onCancel={onClose}>
      <div className="modal-title">
        <h2 id={id}>{title}</h2>
        <button className="icon-button" onClick={onClose} aria-label="Fermer">
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
  label = "Enregistrer",
  onSuccess,
}: {
  onSubmit: (form: FormData) => Promise<unknown>;
  children?: ReactNode;
  label?: string;
  onSuccess?: () => void;
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
      setSuccess("Enregistrement effectué.");
      onSuccess?.();
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
      locked.current = false;
    }
  }
  return (
    <form onSubmit={submit}>
      <Alert error={error} success={success} />
      {children}
      <button className="btn_one" disabled={busy}>
        {busy ? "Veuillez patienter…" : label}
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
