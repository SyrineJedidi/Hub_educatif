import { useEffect, useId, useRef, useState } from "react";
import { ApiError } from "../api/client";
import { Alert } from "../components/UI";
import { transcribe } from "./api";
import { clock } from "./format";
import { useVoiceRecorder, voiceSupported } from "./useVoiceRecorder";
const languages: [string, string][] = [
  ["", "Détection automatique"],
  ["fr", "Français"],
  ["en", "Anglais"],
  ["ar", "Arabe"],
];
export default function VoiceRecorder({
  available = true,
  maxSeconds = 60,
  maxMb = 5,
  locked,
  onTranscript,
  announce,
}: {
  available?: boolean;
  maxSeconds?: number;
  maxMb?: number;
  locked: boolean;
  onTranscript: (text: string) => void;
  announce: (text: string) => void;
}) {
  const [supported] = useState(voiceSupported);
  const [language, setLanguage] = useState(""),
    [uploading, setUploading] = useState(false),
    [failure, setFailure] = useState<unknown>();
  const pending = useRef<Blob | null>(null),
    attempt = useRef(0),
    mounted = useRef(true);
  const id = useId();
  const recorder = useVoiceRecorder({
    maxSeconds,
    onLimit: () =>
      announce("Durée maximale atteinte : l’enregistrement est arrêté."),
    onRecorded: (audio, seconds) => {
      if (!audio.size) {
        recorder.setError("Aucun son n’a été capté. Vérifiez votre micro.");
        return;
      }
      if (seconds < 1) {
        recorder.setError(
          "Enregistrement trop court : parlez au moins une seconde.",
        );
        return;
      }
      if (audio.size > maxMb * 1024 * 1024) {
        recorder.setError(
          "Enregistrement trop volumineux (" +
            new Intl.NumberFormat("fr-FR").format(maxMb) +
            " Mo maximum).",
        );
        return;
      }
      pending.current = audio;
      void upload();
    },
  });
  const recording = recorder.state === "recording",
    cancel = recorder.cancel;
  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  }, []);
  useEffect(() => {
    if (!recording) return;
    const escape = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.preventDefault();
        cancel();
        announce("Enregistrement annulé.");
      }
    };
    document.addEventListener("keydown", escape);
    return () => document.removeEventListener("keydown", escape);
  }, [recording, cancel, announce]);
  async function upload() {
    const audio = pending.current;
    if (!audio) return;
    const current = ++attempt.current;
    setUploading(true);
    setFailure(undefined);
    announce("Enregistrement terminé. Transcription en cours…");
    try {
      const result = await transcribe(audio, language);
      if (!mounted.current || current !== attempt.current) return;
      pending.current = null;
      onTranscript(result.text);
      announce(
        "Transcription ajoutée à votre question : relisez-la avant de l’envoyer.",
      );
    } catch (e) {
      if (mounted.current && current === attempt.current) setFailure(e);
    } finally {
      if (mounted.current && current === attempt.current) setUploading(false);
    }
  }
  function abandon() {
    attempt.current++;
    pending.current = null;
    setUploading(false);
    setFailure(undefined);
    announce("Enregistrement abandonné.");
  }
  if (!available)
    return (
      <p className="field-help assistant-voice-note">
        La dictée vocale n’est pas disponible pour le moment : écrivez votre
        question.
      </p>
    );
  if (!supported)
    return (
      <p className="field-help assistant-voice-note">
        La dictée vocale demande un navigateur récent et une connexion sécurisée
        (HTTPS). Vous pouvez écrire votre question.
      </p>
    );
  const busy = recorder.state === "starting" || uploading;
  // A refused or unreadable recording fails again: only outages are worth a retry.
  const retryable =
    !(failure instanceof ApiError) ||
    failure.status === 0 ||
    failure.status >= 500;
  return (
    <div className="assistant-voice">
      <div className="assistant-voice-controls">
        <button
          type="button"
          className={
            "assistant-voice-button" + (recording ? " is-recording" : "")
          }
          aria-disabled={busy || (locked && !recording) ? true : undefined}
          onClick={() => {
            if (recording) recorder.stop();
            else if (!busy && !locked) {
              setFailure(undefined);
              void recorder.start();
            }
          }}
        >
          <span
            className={recording ? "ti-control-stop" : "ti-microphone"}
            aria-hidden="true"
          />{" "}
          {recording ? "Arrêter l’enregistrement" : "Dicter une question"}
        </button>
        {recording ? (
          <>
            <span className="assistant-recording">
              <span className="assistant-recording-dot" aria-hidden="true" />
              Enregistrement en cours
            </span>
            <span
              className="assistant-timer"
              role="timer"
              aria-label="Durée de l’enregistrement"
            >
              {clock(recorder.elapsed)} / {clock(maxSeconds)}
            </span>
            <button
              type="button"
              className="text-button"
              onClick={() => {
                recorder.cancel();
                announce("Enregistrement annulé.");
              }}
            >
              Annuler<span className="visually-hidden"> l’enregistrement</span>
            </button>
          </>
        ) : (
          <div className="assistant-voice-language">
            <label htmlFor={id}>Langue de la dictée</label>
            <select
              id={id}
              value={language}
              onChange={(e) => setLanguage(e.target.value)}
            >
              {languages.map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
          </div>
        )}
      </div>
      {recorder.state === "starting" && (
        <p className="field-help">Autorisez l’accès au micro pour commencer…</p>
      )}
      {uploading && <p className="field-help">Transcription en cours…</p>}
      {recording && (
        <p className="field-help">
          Échap pour annuler. L’enregistrement s’arrête seul après {maxSeconds}{" "}
          secondes ; l’audio n’est pas conservé.
        </p>
      )}
      {recorder.error && (
        <p className="field-help notice-error" role="alert">
          {recorder.error}
        </p>
      )}
      {!!failure && (
        <div className="assistant-voice-failure">
          <Alert error={failure} />
          <div className="actions">
            {retryable && (
              <button
                type="button"
                className="text-button"
                onClick={() => void upload()}
              >
                Réessayer la transcription
              </button>
            )}
            <button type="button" className="text-button" onClick={abandon}>
              Abandonner l’enregistrement
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
