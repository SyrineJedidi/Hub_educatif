import { api, ApiError, csrf, query } from "../api/client";
import type {
  Conversation,
  Feedback,
  FeedbackInput,
  InputMode,
  ManagedScope,
  Message,
  MessagePage,
  Mode,
  Note,
  Review,
  ReviewAction,
  SendResult,
  SettingsInput,
  SourceType,
  Transcription,
} from "./types";

const OFFLINE =
  "Le serveur est injoignable. Vérifiez votre connexion puis réessayez.";
// A chat tab stays open for hours: a token rotated by a login in another tab
// is refreshed once, and a network failure while fetching it stays in French.
async function write<T>(path: string, method: string, body?: unknown) {
  try {
    return await api<T>(path, method, body);
  } catch (e) {
    if (e instanceof ApiError && e.status === 403 && e.code === "csrf_failed") {
      try {
        await csrf();
      } catch {
        throw new ApiError(0, OFFLINE);
      }
      return api<T>(path, method, body);
    }
    // Only the token fetch can throw something else: a network error or a non-JSON page.
    if (!(e instanceof ApiError)) throw new ApiError(0, OFFLINE);
    throw e;
  }
}
const conversation = (id: string) => "assistant/conversations/" + id + "/";

export const scopesPath = "assistant/scopes/";
export const conversationsPath = (filters: {
  q: string;
  scope: string;
  status: string;
  ordering: string;
  page: number;
}) => "assistant/conversations/?" + query(filters);
export const createConversation = (body: { scope_key: string; mode?: Mode }) =>
  write<Conversation>("assistant/conversations/", "POST", body);
export const getConversation = (id: string) =>
  api<Conversation>(conversation(id));
export const updateConversation = (
  id: string,
  body: Partial<{
    title: string;
    pinned: boolean;
    status: "ACTIVE" | "ARCHIVED";
    mode: Mode;
  }>,
) => write<Conversation>(conversation(id), "PATCH", body);
export const deleteConversation = (id: string) =>
  write<Conversation>(conversation(id), "DELETE");
export const restoreConversation = (id: string) =>
  write<Conversation>(conversation(id) + "restore/", "POST", {});
export const listMessages = (id: string, before = "") =>
  api<MessagePage>(
    conversation(id) + "messages/?" + query({ before, limit: 30 }),
  );
export const sendMessage = (
  id: string,
  body: { content: string; input_mode: InputMode; client_id: string },
) => write<SendResult>(conversation(id) + "messages/", "POST", body);
export const exportUrl = (id: string) => "/api/" + conversation(id) + "export/";

// The endpoint answers with the whole message; only its feedback is needed.
export async function saveFeedback(
  messageId: string,
  body: FeedbackInput,
): Promise<Feedback> {
  const message = await write<Message>(
    "assistant/messages/" + messageId + "/feedback/",
    "PUT",
    body,
  );
  return (
    message.feedback || {
      ...body,
      status: "NEW",
      status_label: "Nouveau",
      teacher_note: "",
    }
  );
}
export const deleteFeedback = (messageId: string) =>
  write<null>("assistant/messages/" + messageId + "/feedback/", "DELETE");

export function audioFileName(type: string) {
  const base = type.split(";")[0].trim();
  const ext = base.endsWith("mp4")
    ? "m4a"
    : base.endsWith("mpeg")
      ? "mp3"
      : base.split("/")[1] || "webm";
  return "question." + ext;
}
export function transcribe(audio: Blob, language: string) {
  const form = new FormData();
  form.append("audio", audio, audioFileName(audio.type));
  if (language) form.append("language", language);
  return write<Transcription>("assistant/transcriptions/", "POST", form);
}

export const notesPath = (group: string, page: number) =>
  "assistant/notes/?" + query({ group, page });
export const createNote = (body: {
  group_id: string;
  title: string;
  body: string;
}) => write<Note>("assistant/notes/", "POST", body);
export const updateNote = (id: string, body: { title: string; body: string }) =>
  write<Note>("assistant/notes/" + id + "/", "PATCH", body);
export const deleteNote = (id: string) =>
  write<null>("assistant/notes/" + id + "/", "DELETE");

export const settingsListPath = "assistant/settings/";
const settingsPath = (sourceType: SourceType, scopeId: string) =>
  "assistant/settings/" + sourceType + "/" + scopeId + "/";
export const saveSettings = (
  sourceType: SourceType,
  scopeId: string,
  body: SettingsInput,
) => write<ManagedScope>(settingsPath(sourceType, scopeId), "PUT", body);

export const insightsPath = (
  sourceType: string,
  scopeId: string,
  range: { from: string; to: string },
) => "assistant/insights/" + sourceType + "/" + scopeId + "/?" + query(range);
export const insightsCsvUrl = (
  sourceType: string,
  scopeId: string,
  range: { from: string; to: string },
) =>
  "/api/assistant/insights/" +
  sourceType +
  "/" +
  scopeId +
  "/?" +
  query({ ...range, format: "csv" });

export const reviewsPath = (filters: {
  status: string;
  scope: string;
  reason: string;
  page: number;
}) => "assistant/reviews/?" + query(filters);
export const reviewPath = (id: string) => "assistant/reviews/" + id + "/";
export const actOnReview = (
  id: string,
  body: { action: ReviewAction; correction?: string; note?: string },
) => write<Review>(reviewPath(id), "PATCH", body);

export const usagePath = "assistant/admin/usage/";
