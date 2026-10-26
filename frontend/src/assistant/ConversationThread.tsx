import { useEffect, useId, useLayoutEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { ApiError, date } from "../api/client";
import { Alert, Empty, Loading, Select } from "../components/UI";
import {
  createConversation,
  getConversation,
  listMessages,
  sendMessage,
  updateConversation,
} from "./api";
import Composer from "./Composer";
import ConversationActions from "./ConversationActions";
import MessageItem, { PendingQuestion, StatusBadge } from "./MessageItem";
import type { Pending } from "./MessageItem";
import VoiceRecorder from "./VoiceRecorder";
import type {
  Conversation,
  Feedback,
  InputMode,
  Message,
  Mode,
  Quota,
  Scope,
  VoiceSettings,
} from "./types";
import { modeHelp, modes, QUESTION_MAX, sourceTypes } from "./types";
import { excerpt, newClientId, plural } from "./format";
const SCOPE_LOST =
  "Ce cours n’est plus accessible : la conversation est en lecture seule.";
const DISABLED =
  "L’assistant est désactivé pour ce cours par votre enseignant.";
function announcement(answer: Message) {
  const prefix =
    answer.status === "OUT_OF_SCOPE"
      ? "Hors cours : "
      : answer.status === "FAILED"
        ? "Échec : "
        : answer.status === "BLOCKED"
          ? "Réponse bloquée : "
          : "Réponse de l’assistant : ";
  const sources = answer.citations.length;
  return (
    prefix +
    excerpt(answer.content) +
    (sources
      ? " " + plural(sources, "source citée", "sources citées") + "."
      : "")
  );
}
function ModeControl({
  mode,
  choice,
  draft,
  fixedByTeacher,
  onChange,
}: {
  mode: Mode;
  choice: boolean;
  draft: boolean;
  fixedByTeacher: boolean;
  onChange: (mode: Mode) => void;
}) {
  const id = useId();
  const values = Object.keys(modes) as Mode[];
  if (!choice)
    return (
      <p className="field-help assistant-mode-fixed">
        Mode de réponse : {modes[mode]}
        {fixedByTeacher ? " (choisi par votre enseignant)." : "."}{" "}
        {modeHelp[mode]}
      </p>
    );
  // A new conversation shows both modes side by side; afterwards a compact select is enough.
  if (draft)
    return (
      <fieldset className="assistant-modes">
        <legend>Mode de réponse</legend>
        {values.map((value) => (
          <label key={value} className="assistant-mode">
            <input
              type="radio"
              name={id}
              value={value}
              checked={mode === value}
              onChange={() => onChange(value)}
            />
            <span>
              <strong>{modes[value]}</strong>
              <small>{modeHelp[value]}</small>
            </span>
          </label>
        ))}
      </fieldset>
    );
  return (
    <div className="assistant-mode-select">
      <Select
        label="Mode de réponse"
        value={mode}
        aria-describedby={id}
        onChange={(e) => onChange(e.target.value as Mode)}
      >
        {values.map((value) => (
          <option key={value} value={value}>
            {modes[value]}
          </option>
        ))}
      </Select>
      <p id={id} className="field-help">
        {modeHelp[mode]}
      </p>
    </div>
  );
}
export default function ConversationThread({
  conversationId,
  scopes,
  voice,
  quotas,
  initialScope,
  initialDraft,
  teacher,
  focusHeading,
  onDraft,
  onCreated,
  onChanged,
  onDeleted,
  onScope,
  onQuota,
  onQuotaStale,
  onNew,
  announce,
}: {
  conversationId: string | null;
  scopes: Scope[];
  voice?: VoiceSettings;
  quotas: Record<string, Quota>;
  initialScope: string;
  initialDraft: string;
  teacher: boolean;
  focusHeading: boolean;
  onDraft: (text: string) => void;
  onCreated: (conversation: Conversation) => void;
  onChanged: (conversation: Conversation) => void;
  onDeleted: () => void;
  onScope: (key: string) => void;
  onQuota: (key: string, quota: Quota) => void;
  onQuotaStale: () => void;
  onNew: () => void;
  announce: (text: string) => void;
}) {
  const [conversation, setConversation] = useState<Conversation | null>(null),
    [messages, setMessages] = useState<Message[]>([]),
    [hasMore, setHasMore] = useState(false),
    [loading, setLoading] = useState(!!conversationId),
    [loadError, setLoadError] = useState<unknown>(),
    [revision, setRevision] = useState(0);
  const [older, setOlder] = useState(false),
    [olderError, setOlderError] = useState<unknown>();
  const [pending, setPending] = useState<Pending[]>([]),
    [draft, setDraftState] = useState(initialDraft),
    [inputMode, setInputMode] = useState<InputMode>("TEXT"),
    [composerError, setComposerError] = useState(""),
    [lock, setLock] = useState(""),
    [sending, setSending] = useState(false);
  const [scopeKey, setScopeKey] = useState(
    () =>
      (scopes.some((s) => s.key === initialScope) && initialScope) ||
      scopes[0]?.key ||
      "",
  );
  const [draftMode, setDraftMode] = useState<Mode | "">(""),
    [modeBusy, setModeBusy] = useState(false),
    [modeError, setModeError] = useState<unknown>();
  const transcript = useRef<HTMLElement>(null),
    textarea = useRef<HTMLTextAreaElement>(null),
    heading = useRef<HTMLHeadingElement>(null),
    sendingNow = useRef(false),
    stick = useRef(true),
    restore = useRef<{ height: number; top: number } | null>(null);
  const id = useId();
  const currentKey = conversation?.scope_key || scopeKey;
  const scope = scopes.find((s) => s.key === currentKey);
  const quota = quotas[currentKey];
  const mode: Mode = conversation
    ? conversation.mode
    : draftMode || scope?.default_mode || "EXPLICATION";

  useEffect(() => {
    // A conversation created by this thread is already in state: no reload.
    if (!conversationId || conversation?.id === conversationId) return;
    let active = true;
    setLoading(true);
    setLoadError(undefined);
    Promise.all([getConversation(conversationId), listMessages(conversationId)])
      .then(([loaded, page]) => {
        if (!active) return;
        stick.current = true;
        setConversation(loaded);
        setMessages(page.results);
        setHasMore(page.has_more);
      })
      .catch((e) => {
        if (active) setLoadError(e);
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [conversationId, revision]);
  useEffect(() => {
    onScope(currentKey);
  }, [currentKey]);
  useEffect(() => {
    if (focusHeading && !loading) heading.current?.focus();
  }, [focusHeading, loading]);
  useLayoutEffect(() => {
    const el = transcript.current;
    if (!el) return;
    if (restore.current) {
      el.scrollTop =
        el.scrollHeight - restore.current.height + restore.current.top;
      restore.current = null;
    } else if (stick.current) el.scrollTop = el.scrollHeight;
  }, [messages, pending, loading]);

  function setDraft(text: string) {
    setDraftState(text);
    onDraft(text);
    if (!text.trim()) setInputMode("TEXT");
  }
  function fill(text: string, append = true) {
    const next = append && draft.trim() ? draft.trimEnd() + "\n" + text : text;
    setDraft(next);
    setComposerError("");
    requestAnimationFrame(() => {
      const el = textarea.current;
      el?.focus();
      el?.setSelectionRange(next.length, next.length);
    });
  }
  const status = conversation?.status;
  const showComposer = conversation ? status === "ACTIVE" : scopes.length > 0;
  const lockMessage =
    lock ||
    (conversation && !conversation.can_send
      ? scope && !scope.enabled
        ? DISABLED
        : SCOPE_LOST
      : scope && !scope.enabled
        ? DISABLED
        : quota && quota.remaining <= 0
          ? "Vous avez atteint la limite de " +
            plural(quota.limit, "question", "questions") +
            " pour aujourd’hui sur ce cours. Elle sera réinitialisée demain."
          : "");
  const locked = !!lockMessage;

  function handleError(e: unknown) {
    if (!(e instanceof ApiError)) return;
    if (e.code === "conversation_locked" && conversation)
      void getConversation(conversation.id)
        .then((latest) => {
          setConversation(latest);
          onChanged(latest);
        })
        .catch(() => undefined);
    if (e.code === "scope_unavailable" || e.code === "assistant_disabled") {
      setLock(e.message);
      setConversation((c) => (c ? { ...c, can_send: false } : c));
      onQuotaStale();
    }
    if (e.code === "quota_exceeded") onQuotaStale();
  }
  async function send(content: string, input: InputMode, retry?: Pending) {
    if (sendingNow.current) return;
    sendingNow.current = true;
    setSending(true);
    setComposerError("");
    const item: Pending = retry
      ? { ...retry, state: "sending", error: undefined }
      : {
          key: newClientId(),
          clientId: newClientId(),
          content,
          inputMode: input,
          state: "sending",
        };
    setPending((list) =>
      retry
        ? list.map((p) => (p.key === item.key ? item : p))
        : [...list, item],
    );
    stick.current = true;
    announce("Question envoyée. L’assistant rédige une réponse…");
    try {
      let current = conversation;
      if (!current) {
        if (!scope)
          throw new ApiError(400, "Choisissez un cours pour commencer.");
        current = await createConversation({
          scope_key: scope.key,
          ...(scope.allow_mode_choice ? { mode } : {}),
        });
        setConversation(current);
        onCreated(current);
      }
      const result = await sendMessage(current.id, {
        content: item.content,
        input_mode: item.inputMode,
        client_id: item.clientId,
      });
      setMessages((list) => [
        ...list.filter(
          (m) => m.id !== result.question.id && m.id !== result.answer.id,
        ),
        result.question,
        result.answer,
      ]);
      setPending((list) => list.filter((p) => p.key !== item.key));
      setConversation(result.conversation);
      onChanged(result.conversation);
      if (result.quota) onQuota(result.conversation.scope_key, result.quota);
      announce(announcement(result.answer));
    } catch (e) {
      setPending((list) =>
        list.map((p) =>
          p.key === item.key ? { ...p, state: "error", error: e } : p,
        ),
      );
      handleError(e);
    } finally {
      sendingNow.current = false;
      setSending(false);
    }
  }
  function submit() {
    if (locked) return;
    if (sendingNow.current) {
      setComposerError(
        "Patientez : l’assistant rédige encore la réponse précédente.",
      );
      return;
    }
    const content = draft.trim();
    if (!content) {
      setComposerError("Écrivez votre question avant de l’envoyer.");
      textarea.current?.focus();
      return;
    }
    if (content.length > QUESTION_MAX) {
      setComposerError("Votre question dépasse 2 000 caractères.");
      return;
    }
    const input = inputMode;
    setDraft("");
    setInputMode("TEXT");
    void send(content, input);
  }
  function edit(item: Pending) {
    setPending((list) => list.filter((p) => p.key !== item.key));
    setInputMode(item.inputMode);
    fill(item.content);
  }
  async function loadOlder() {
    if (older || !conversation || !messages.length) return;
    setOlder(true);
    setOlderError(undefined);
    try {
      const page = await listMessages(conversation.id, messages[0].id);
      const el = transcript.current;
      restore.current = el
        ? { height: el.scrollHeight, top: el.scrollTop }
        : null;
      setMessages((list) => [
        ...page.results.filter((m) => !list.some((x) => x.id === m.id)),
        ...list,
      ]);
      setHasMore(page.has_more);
      if (!page.has_more) transcript.current?.focus({ preventScroll: true });
    } catch (e) {
      setOlderError(e);
    } finally {
      setOlder(false);
    }
  }
  async function changeMode(next: Mode) {
    if (!conversation) {
      setDraftMode(next);
      return;
    }
    if (modeBusy) return;
    setModeBusy(true);
    setModeError(undefined);
    try {
      const updated = await updateConversation(conversation.id, {
        mode: next,
      });
      setConversation(updated);
      onChanged(updated);
      announce("Mode de réponse : " + modes[next] + ".");
    } catch (e) {
      setModeError(e);
    } finally {
      setModeBusy(false);
    }
  }
  function updateFeedback(messageId: string, feedback: Feedback | null) {
    setMessages((list) =>
      list.map((m) => (m.id === messageId ? { ...m, feedback } : m)),
    );
  }
  function changed(updated: Conversation) {
    setConversation(updated);
    onChanged(updated);
  }

  if (conversationId && !conversation)
    return (
      <section className="panel assistant-thread" aria-labelledby={id + "-h"}>
        {loading ? (
          <>
            <h2 id={id + "-h"} ref={heading} tabIndex={-1}>
              Conversation
            </h2>
            <Loading />
          </>
        ) : (
          <>
            <h2 id={id + "-h"} ref={heading} tabIndex={-1}>
              {loadError instanceof ApiError && loadError.status === 404
                ? "Conversation introuvable"
                : "Conversation indisponible"}
            </h2>
            {loadError instanceof ApiError && loadError.status === 404 ? (
              <p>
                Cette conversation n’existe pas ou a été supprimée
                définitivement.
              </p>
            ) : (
              <Alert error={loadError} />
            )}
            <div className="actions">
              {!(loadError instanceof ApiError && loadError.status === 404) && (
                <button
                  className="text-button"
                  onClick={() => setRevision((n) => n + 1)}
                >
                  Réessayer le chargement
                </button>
              )}
              <button className="btn_one" onClick={onNew}>
                Nouvelle conversation +
              </button>
            </div>
          </>
        )}
      </section>
    );

  let assistantCount = 0,
    lastQuestion: Message | undefined;
  const last = messages[messages.length - 1];
  const empty = !messages.length && !pending.length;
  return (
    <section className="panel assistant-thread" aria-labelledby={id + "-h"}>
      <div className="assistant-thread-head">
        <div>
          {scope || conversation ? (
            <p className="eyebrow">
              {sourceTypes[conversation?.source_type || scope!.source_type]} ·{" "}
              {conversation?.scope_title || scope?.title}
            </p>
          ) : null}
          <h2 id={id + "-h"} ref={heading} tabIndex={-1}>
            {conversation?.title || "Nouvelle conversation"}
          </h2>
          {conversation && conversation.status !== "ACTIVE" && (
            <p className="assistant-badges">
              <StatusBadge kind="info">
                {conversation.status_label ||
                  (conversation.status === "ARCHIVED"
                    ? "Archivée"
                    : "Corbeille")}
              </StatusBadge>
            </p>
          )}
        </div>
        {conversation && (
          <ConversationActions
            conversation={conversation}
            onChange={changed}
            onDeleted={(deleted) => {
              onChanged(deleted);
              onDeleted();
            }}
            onRestored={(restored) => {
              changed(restored);
              requestAnimationFrame(() => heading.current?.focus());
            }}
            announce={announce}
          />
        )}
      </div>
      {!conversation && scopes.length === 0 ? (
        <>
          <Empty title="Aucun cours disponible pour l’assistant">
            {teacher
              ? "Rédigez une note de cours pour l’un de vos groupes, ou publiez un cours, pour pouvoir interroger l’assistant."
              : "Vos enseignants n’ont pas encore partagé de contenu exploitable par l’assistant. Revenez plus tard."}
          </Empty>
          {teacher && (
            <p className="assistant-empty-action">
              <Link className="btn_one" to="/espace/assistant/notes">
                Rédiger une note de cours +
              </Link>
            </p>
          )}
        </>
      ) : (
        <div className="assistant-settings-row">
          {!conversation && (
            <Select
              label="Cours"
              value={scopeKey}
              onChange={(e) => {
                setScopeKey(e.target.value);
                setDraftMode("");
                setLock("");
              }}
            >
              {scopes.map((s) => (
                <option key={s.key} value={s.key}>
                  {s.title} · {sourceTypes[s.source_type]}
                </option>
              ))}
            </Select>
          )}
          <ModeControl
            mode={mode}
            choice={
              !!scope?.allow_mode_choice &&
              (!conversation ||
                (conversation.status === "ACTIVE" && conversation.can_send))
            }
            draft={!conversation}
            fixedByTeacher={!!scope && !scope.allow_mode_choice}
            onChange={(next) => void changeMode(next)}
          />
          <Alert error={modeError} />
        </div>
      )}
      {(conversation || scopes.length > 0) && (
        <section
          ref={transcript}
          className="assistant-transcript"
          aria-label="Fil de la conversation"
          tabIndex={0}
          onScroll={(e) => {
            const el = e.currentTarget;
            stick.current =
              el.scrollHeight - el.scrollTop - el.clientHeight < 80;
          }}
        >
          {hasMore && (
            <div className="assistant-older">
              <button
                className="text-button"
                aria-disabled={older ? true : undefined}
                onClick={() => void loadOlder()}
              >
                {older
                  ? "Chargement des messages…"
                  : "Afficher les messages précédents"}
              </button>
              <Alert error={olderError} />
            </div>
          )}
          {empty && scope && (
            <div className="assistant-welcome">
              <p className="assistant-pre">
                {scope.welcome_message ||
                  "Bonjour ! Posez une question sur « " +
                    scope.title +
                    " » : je réponds uniquement à partir du contenu du cours et je cite mes sources."}
              </p>
              {scope.suggested_questions.length > 0 && showComposer && (
                <>
                  <p className="assistant-welcome-label">
                    Questions suggérées par votre enseignant :
                  </p>
                  <ul className="assistant-chips">
                    {scope.suggested_questions.map((text) => (
                      <li key={text}>
                        <button type="button" onClick={() => fill(text, false)}>
                          {text}
                        </button>
                      </li>
                    ))}
                  </ul>
                </>
              )}
            </div>
          )}
          {empty && !scope && conversation && (
            <p className="field-help">Aucun message dans cette conversation.</p>
          )}
          {!empty && (
            <ol className="assistant-messages">
              {messages.map((message) => {
                if (message.role === "USER") lastQuestion = message;
                else assistantCount++;
                return (
                  <li key={message.id}>
                    <MessageItem
                      message={message}
                      ordinal={assistantCount}
                      question={
                        message.role === "USER"
                          ? undefined
                          : messages.find(
                              (m) => m.id === message.reply_to_id,
                            ) || lastQuestion
                      }
                      showFollowUps={
                        message === last &&
                        !pending.length &&
                        showComposer &&
                        !locked
                      }
                      canRetry={showComposer && !locked && !sending}
                      canFeedback={status !== "DELETED"}
                      teacher={teacher}
                      onRetry={(q) => void send(q.content, q.input_mode)}
                      onFollowUp={(text) => fill(text)}
                      onFeedback={updateFeedback}
                      announce={announce}
                    />
                  </li>
                );
              })}
              {pending.map((item) => (
                <li key={item.key}>
                  <PendingQuestion
                    item={item}
                    canResend={!sending && !locked}
                    onResend={() =>
                      void send(item.content, item.inputMode, item)
                    }
                    onEdit={() => edit(item)}
                  />
                </li>
              ))}
              {pending.some((item) => item.state === "sending") && (
                <li className="assistant-typing">
                  <span className="assistant-typing-dots" aria-hidden="true">
                    <span />
                    <span />
                    <span />
                  </span>
                  L’assistant rédige une réponse…
                </li>
              )}
            </ol>
          )}
        </section>
      )}
      {conversation?.status === "ARCHIVED" && (
        <p className="notice">
          Conversation archivée : elle est en lecture seule. Désarchivez-la pour
          poser de nouvelles questions.
        </p>
      )}
      {conversation?.status === "DELETED" && (
        <p className="notice">
          Cette conversation est dans la corbeille
          {conversation.purge_at
            ? " jusqu’au " + date(conversation.purge_at)
            : ""}
          . Restaurez-la pour la retrouver parmi vos conversations actives.
        </p>
      )}
      {showComposer && (
        <Composer
          value={draft}
          onChange={(text) => {
            setDraft(text);
            if (composerError) setComposerError("");
          }}
          onSubmit={submit}
          busy={sending}
          locked={locked}
          lockMessage={lockMessage}
          error={composerError}
          textareaRef={textarea}
          voice={
            <VoiceRecorder
              available={voice?.available ?? true}
              maxSeconds={voice?.max_seconds || 60}
              maxMb={voice?.max_mb || 5}
              locked={locked}
              announce={announce}
              onTranscript={(text) => {
                fill(text);
                setInputMode("VOICE");
              }}
            />
          }
        />
      )}
    </section>
  );
}
