import { Link } from "react-router-dom";
import { date } from "../api/client";
import type { Page } from "../api/types";
import { Alert, Field, Loading, Pagination, Select } from "../components/UI";
import type { Conversation, Scope } from "./types";
import { plural } from "./format";
export interface ListFilters {
  search: string;
  scope: string;
  status: "active" | "archived" | "deleted";
  ordering: string;
  page: number;
}
const tabs: [ListFilters["status"], string][] = [
  ["active", "Actives"],
  ["archived", "Archivées"],
  ["deleted", "Corbeille"],
];
const orderings: [string, string][] = [
  ["-last_message_at", "Activité récente"],
  ["-created_at", "Date de création"],
  ["title", "Titre"],
];
export default function ConversationList({
  scopes,
  data,
  loading,
  error,
  reload,
  filters,
  onFilters,
  selectedId,
  onSelect,
  onNew,
}: {
  scopes: Scope[];
  data: Page<Conversation> | null;
  loading: boolean;
  error: unknown;
  reload: () => void;
  filters: ListFilters;
  onFilters: (patch: Partial<ListFilters>) => void;
  selectedId: string | null;
  onSelect: (id: string) => void;
  onNew: () => void;
}) {
  const filtered = !!(filters.search.trim() || filters.scope);
  return (
    <nav className="assistant-list" aria-label="Mes conversations">
      <div className="assistant-list-head">
        <h2>Mes conversations</h2>
        <button className="btn_one" onClick={onNew}>
          Nouvelle conversation +
        </button>
      </div>
      <div
        className="assistant-tabs"
        role="group"
        aria-label="Afficher les conversations"
      >
        {tabs.map(([value, label]) => (
          <button
            key={value}
            aria-pressed={filters.status === value}
            onClick={() => onFilters({ status: value, page: 1 })}
          >
            {label}
          </button>
        ))}
      </div>
      <Field
        label="Rechercher"
        type="search"
        maxLength={100}
        value={filters.search}
        placeholder="Titre ou contenu d’un message"
        onChange={(e) => onFilters({ search: e.target.value, page: 1 })}
      />
      <div className="assistant-list-filters">
        <Select
          label="Cours"
          value={filters.scope}
          onChange={(e) => onFilters({ scope: e.target.value, page: 1 })}
        >
          <option value="">Tous les cours</option>
          {scopes.map((scope) => (
            <option key={scope.key} value={scope.key}>
              {scope.title}
            </option>
          ))}
        </Select>
        <Select
          label="Trier par"
          value={filters.ordering}
          onChange={(e) => onFilters({ ordering: e.target.value, page: 1 })}
        >
          {orderings.map(([value, label]) => (
            <option key={value} value={value}>
              {label}
            </option>
          ))}
        </Select>
      </div>
      {filters.status === "deleted" && (
        <p className="field-help">
          Les conversations de la corbeille sont supprimées définitivement 30
          jours après leur suppression.
        </p>
      )}
      {loading && !data ? (
        <Loading />
      ) : !data ? (
        <div>
          <Alert error={error} />
          <button className="text-button" onClick={reload}>
            Réessayer le chargement
          </button>
        </div>
      ) : (
        <>
          <Alert error={error} />
          <p className="field-help" role="status">
            {data.count
              ? plural(data.count, "conversation", "conversations")
              : filtered
                ? "Aucune conversation ne correspond à ces critères."
                : filters.status === "active"
                  ? "Aucune conversation pour le moment : posez votre première question."
                  : filters.status === "archived"
                    ? "Aucune conversation archivée."
                    : "La corbeille est vide."}
          </p>
          {data.results.length > 0 && (
            <ul className="assistant-conversations">
              {data.results.map((conversation) => (
                <li key={conversation.id}>
                  <Link
                    to={{ search: "?conversation=" + conversation.id }}
                    aria-current={
                      conversation.id === selectedId ? "page" : undefined
                    }
                    onClick={() => onSelect(conversation.id)}
                  >
                    <span className="assistant-conversation-title">
                      {conversation.pinned && (
                        <>
                          <span className="ti-pin-alt" aria-hidden="true" />
                          <span className="visually-hidden">Épinglée : </span>
                        </>
                      )}
                      {conversation.title || "Nouvelle conversation"}
                    </span>
                    <small>{conversation.scope_title}</small>
                    <small>
                      {date(
                        conversation.last_message_at || conversation.created_at,
                      )}{" "}
                      ·{" "}
                      {plural(
                        conversation.message_count,
                        "message",
                        "messages",
                      )}
                    </small>
                  </Link>
                </li>
              ))}
            </ul>
          )}
          <Pagination
            page={filters.page}
            count={data.count}
            onChange={(page) => onFilters({ page })}
          />
          {filtered && (
            <button
              className="text-button"
              onClick={() => onFilters({ search: "", scope: "", page: 1 })}
            >
              Réinitialiser les filtres
            </button>
          )}
        </>
      )}
    </nav>
  );
}
