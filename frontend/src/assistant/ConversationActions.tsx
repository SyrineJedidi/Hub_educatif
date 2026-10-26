import { useState } from "react";
import { date } from "../api/client";
import { Alert, Field, Form, Modal, val } from "../components/UI";
import {
  deleteConversation,
  exportUrl,
  restoreConversation,
  updateConversation,
} from "./api";
import type { Conversation } from "./types";
export default function ConversationActions({
  conversation,
  onChange,
  onDeleted,
  onRestored,
  announce,
}: {
  conversation: Conversation;
  onChange: (conversation: Conversation) => void;
  onDeleted: (conversation: Conversation) => void;
  onRestored: (conversation: Conversation) => void;
  announce: (text: string) => void;
}) {
  const [modal, setModal] = useState<"rename" | "delete" | null>(null),
    [busy, setBusy] = useState(false),
    [error, setError] = useState<unknown>();
  const deleted = conversation.status === "DELETED",
    archived = conversation.status === "ARCHIVED";
  async function run(
    action: () => Promise<Conversation>,
    message: string,
    done: (c: Conversation) => void = onChange,
  ) {
    if (busy) return;
    setBusy(true);
    setError(undefined);
    try {
      const updated = await action();
      done(updated);
      announce(message);
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  }
  const exportLink = (
    <a
      className="text-button"
      href={exportUrl(conversation.id)}
      download={"conversation-" + conversation.id + ".md"}
    >
      <span className="ti-download" aria-hidden="true" /> Exporter
      <span className="visually-hidden"> la conversation</span> (Markdown)
    </a>
  );
  return (
    <>
      {deleted ? (
        <div className="actions assistant-actions">
          <button
            className="btn_one"
            aria-disabled={busy ? true : undefined}
            onClick={() =>
              void run(
                () => restoreConversation(conversation.id),
                "Conversation restaurée.",
                onRestored,
              )
            }
          >
            Restaurer la conversation
          </button>
          {exportLink}
          {conversation.purge_at && (
            <p className="assistant-meta">
              Suppression définitive le {date(conversation.purge_at)}.
            </p>
          )}
        </div>
      ) : (
        <div className="actions assistant-actions">
          <button className="text-button" onClick={() => setModal("rename")}>
            <span className="ti-pencil" aria-hidden="true" /> Renommer
            <span className="visually-hidden"> la conversation</span>
          </button>
          <button
            className="text-button"
            aria-disabled={busy ? true : undefined}
            onClick={() =>
              void run(
                () =>
                  updateConversation(conversation.id, {
                    pinned: !conversation.pinned,
                  }),
                conversation.pinned
                  ? "Conversation désépinglée."
                  : "Conversation épinglée en haut de la liste.",
              )
            }
          >
            <span className="ti-pin-alt" aria-hidden="true" />{" "}
            {conversation.pinned ? "Désépingler" : "Épingler"}
          </button>
          <button
            className="text-button"
            aria-disabled={busy ? true : undefined}
            onClick={() =>
              void run(
                () =>
                  updateConversation(conversation.id, {
                    status: archived ? "ACTIVE" : "ARCHIVED",
                  }),
                archived
                  ? "Conversation désarchivée : vous pouvez reprendre l’échange."
                  : "Conversation archivée : elle est désormais en lecture seule.",
              )
            }
          >
            <span className="ti-archive" aria-hidden="true" />{" "}
            {archived ? "Désarchiver" : "Archiver"}
          </button>
          {exportLink}
          <button className="text-button" onClick={() => setModal("delete")}>
            <span className="ti-trash" aria-hidden="true" /> Supprimer
            <span className="visually-hidden"> la conversation</span>
          </button>
        </div>
      )}
      <Alert error={error} />
      {modal === "rename" && (
        <Modal title="Renommer la conversation" onClose={() => setModal(null)}>
          <Form
            label="Enregistrer le titre"
            onSubmit={async (form) => {
              const updated = await updateConversation(conversation.id, {
                title: val(form, "title").trim(),
              });
              onChange(updated);
            }}
            onSuccess={() => {
              setModal(null);
              announce("Conversation renommée.");
            }}
          >
            <Field
              label="Titre"
              name="title"
              required
              maxLength={120}
              defaultValue={conversation.title}
            />
          </Form>
        </Modal>
      )}
      {modal === "delete" && (
        <Modal
          title="Supprimer cette conversation ?"
          onClose={() => setModal(null)}
        >
          <p className="intro">
            La conversation sera placée dans la corbeille. Vous pourrez la
            restaurer pendant 30 jours ; elle sera ensuite supprimée
            définitivement avec ses messages.
          </p>
          <Form
            label="Placer dans la corbeille"
            onSubmit={async () => {
              const updated = await deleteConversation(conversation.id);
              setModal(null);
              onDeleted(updated || { ...conversation, status: "DELETED" });
              announce("Conversation placée dans la corbeille.");
            }}
          />
        </Modal>
      )}
    </>
  );
}
