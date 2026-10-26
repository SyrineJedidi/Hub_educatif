import { useCallback, useEffect, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import type { Page } from "../api/types";
import { useResource } from "../hooks/useResource";
import { Alert, Loading } from "../components/UI";
import { conversationsPath, scopesPath } from "./api";
import ConversationList from "./ConversationList";
import type { ListFilters } from "./ConversationList";
import ConversationThread from "./ConversationThread";
import { AssistantManagerNav } from "./AssistantRoutes";
import { useAssistantContext } from "./useAssistantContext";
import type { Conversation, Quota, ScopeList } from "./types";
import { plural } from "./format";
import "./assistant.css";
const WIDE = "(min-width: 992px)";
function useWide() {
  const [wide, setWide] = useState(() => window.matchMedia(WIDE).matches);
  useEffect(() => {
    const media = window.matchMedia(WIDE);
    const change = () => setWide(media.matches);
    media.addEventListener("change", change);
    return () => media.removeEventListener("change", change);
  }, []);
  return wide;
}
function QuotaIndicator({ quota, title }: { quota?: Quota; title?: string }) {
  if (!quota) return null;
  const limit = Math.max(quota.limit, 0);
  return (
    <div className="assistant-quota">
      <p className="assistant-quota-label">
        Questions aujourd’hui{title ? " · " + title : ""}
      </p>
      <progress
        aria-label="Questions posées aujourd’hui sur ce cours"
        value={Math.min(quota.used, limit)}
        max={Math.max(limit, 1)}
      />
      <p>
        {quota.remaining > 0
          ? plural(
              quota.remaining,
              "question restante",
              "questions restantes",
            ) +
            " sur " +
            limit
          : "Limite du jour atteinte (" + limit + " questions)"}
      </p>
    </div>
  );
}
export default function AssistantPage() {
  const { teacher } = useAssistantContext();
  const wide = useWide();
  const [params, setParams] = useSearchParams();
  const selected = params.get("conversation");
  const scopeParam = params.get("scope") || "";
  const scopes = useResource<ScopeList>(scopesPath);
  const scopeList = scopes.data?.results || [];
  const [quotas, setQuotas] = useState<Record<string, Quota>>({});
  useEffect(() => {
    if (scopes.data)
      setQuotas(
        Object.fromEntries(
          scopes.data.results
            .filter((scope) => scope.quota)
            .map((scope) => [scope.key, scope.quota!]),
        ),
      );
  }, [scopes.data]);
  const [filters, setFilters] = useState<ListFilters>({
    search: "",
    scope: "",
    status: "active",
    ordering: "-last_message_at",
    page: 1,
  });
  const [q, setQ] = useState("");
  useEffect(() => {
    const timer = window.setTimeout(() => setQ(filters.search.trim()), 300);
    return () => window.clearTimeout(timer);
  }, [filters.search]);
  const list = useResource<Page<Conversation>>(
    conversationsPath({
      q,
      scope: filters.scope,
      status: filters.status,
      ordering: filters.ordering === "-last_message_at" ? "" : filters.ordering,
      page: filters.page,
    }),
  );
  // A conversation created by the draft keeps the draft's key, so sending the
  // first question does not remount the composer that has the focus.
  const created = useRef<{ id: string; key: string } | null>(null),
    drafts = useRef(new Map<string, string>());
  const [draftKey, setDraftKey] = useState("draft-0"),
    [focusKey, setFocusKey] = useState(""),
    [listOpen, setListOpen] = useState(false),
    [currentScope, setCurrentScope] = useState("");
  const keyFor = (id: string) =>
    created.current?.id === id ? created.current.key : "conversation-" + id;
  const threadKey = selected ? keyFor(selected) : draftKey;
  useEffect(() => {
    // Focus moves to the thread heading once, not each time it comes back.
    if (focusKey && focusKey !== threadKey) setFocusKey("");
  }, [threadKey]);
  const [message, setMessage] = useState("");
  const timer = useRef(0);
  const announce = useCallback((text: string) => {
    window.clearTimeout(timer.current);
    setMessage("");
    timer.current = window.setTimeout(() => setMessage(text), 80);
  }, []);
  useEffect(() => () => window.clearTimeout(timer.current), []);
  function startNew(focus = false) {
    created.current = null;
    const key = "draft-" + Date.now();
    setDraftKey(key);
    if (focus) setFocusKey(key);
    setListOpen(false);
    setParams((current) => {
      const next = new URLSearchParams(current);
      next.delete("conversation");
      next.delete("scope");
      return next;
    });
  }
  const scopeTitle = scopeList.find((s) => s.key === currentScope)?.title;
  const listNode = (
    <ConversationList
      scopes={scopeList}
      data={list.data}
      loading={list.loading}
      error={list.error}
      reload={list.reload}
      filters={filters}
      onFilters={(patch) => setFilters((current) => ({ ...current, ...patch }))}
      selectedId={selected}
      onSelect={(id) => {
        if (!wide) {
          setListOpen(false);
          setFocusKey(keyFor(id));
        }
      }}
      onNew={() => startNew(true)}
    />
  );
  return (
    <div className="assistant-module">
      <div className="page-heading">
        <div>
          <p className="eyebrow">
            {teacher ? "APERÇU ENSEIGNANT" : "RÉPONSES SOURCÉES"}
          </p>
          <h1>Assistant pédagogique</h1>
          <p>
            {teacher
              ? "Interrogez l’assistant sur vos cours comme le feront vos étudiants. Vos propres questions ne sont pas comptées dans le suivi."
              : "Posez vos questions par écrit ou à voix haute : l’assistant répond à partir de vos cours et cite ses sources."}
          </p>
        </div>
        <QuotaIndicator quota={quotas[currentScope]} title={scopeTitle} />
      </div>
      <AssistantManagerNav />
      <p className="notice assistant-privacy">
        <span className="ti-lock" aria-hidden="true" /> Ne partagez pas
        d’informations personnelles : vos questions sont envoyées au service
        Gemini de Google.
      </p>
      <p
        className="visually-hidden"
        role="status"
        aria-live="polite"
        aria-atomic="true"
      >
        {message}
      </p>
      {!scopes.data && scopes.loading ? (
        <Loading />
      ) : (
        <>
          {!!scopes.error && (
            <div className="notice notice-error assistant-scope-error">
              <Alert error={scopes.error} />
              <button className="text-button" onClick={scopes.reload}>
                Réessayer le chargement des cours
              </button>
            </div>
          )}
          <div className="assistant-layout">
            {wide ? (
              listNode
            ) : (
              <details
                className="assistant-list-details"
                open={listOpen}
                onToggle={(e) => setListOpen(e.currentTarget.open)}
              >
                <summary>
                  Mes conversations
                  {list.data ? " (" + list.data.count + ")" : ""}
                </summary>
                {listNode}
              </details>
            )}
            <ConversationThread
              key={threadKey}
              conversationId={selected}
              scopes={scopeList}
              voice={scopes.data?.voice}
              quotas={quotas}
              initialScope={scopeParam}
              initialDraft={drafts.current.get(threadKey) || ""}
              teacher={teacher}
              focusHeading={focusKey === threadKey}
              onDraft={(text) => drafts.current.set(threadKey, text)}
              onCreated={(conversation) => {
                created.current = { id: conversation.id, key: threadKey };
                setParams(
                  (current) => {
                    const next = new URLSearchParams(current);
                    next.set("conversation", conversation.id);
                    next.delete("scope");
                    return next;
                  },
                  { replace: true },
                );
                list.reload();
              }}
              onChanged={() => list.reload()}
              onDeleted={() => startNew(true)}
              onScope={setCurrentScope}
              onQuota={(key, quota) =>
                setQuotas((current) => ({ ...current, [key]: quota }))
              }
              onQuotaStale={scopes.reload}
              onNew={() => startNew(true)}
              announce={announce}
            />
          </div>
        </>
      )}
    </div>
  );
}
