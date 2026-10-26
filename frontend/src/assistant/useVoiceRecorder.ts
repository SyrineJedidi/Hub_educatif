import { useCallback, useEffect, useRef, useState } from "react";
const MIME_TYPES = [
  "audio/webm;codecs=opus",
  "audio/mp4;codecs=mp4a.40.2",
  "audio/mp4",
  "audio/webm",
];
export function voiceSupported() {
  return (
    typeof window !== "undefined" &&
    window.isSecureContext &&
    !!navigator.mediaDevices?.getUserMedia &&
    typeof MediaRecorder !== "undefined"
  );
}
function microphoneError(error: unknown) {
  const name = error instanceof DOMException ? error.name : "";
  if (name === "NotAllowedError" || name === "SecurityError")
    return "L’accès au micro a été refusé. Autorisez-le depuis l’icône située à gauche de la barre d’adresse, puis réessayez. Vous pouvez toujours écrire votre question.";
  if (name === "NotFoundError" || name === "OverconstrainedError")
    return "Aucun micro n’a été détecté sur cet appareil.";
  if (name === "NotReadableError" || name === "AbortError")
    return "Le micro est utilisé par une autre application ou ne répond pas.";
  return "Impossible de démarrer l’enregistrement sur ce navigateur.";
}
export type RecorderState = "idle" | "starting" | "recording";
export function useVoiceRecorder({
  maxSeconds,
  onRecorded,
  onLimit,
}: {
  maxSeconds: number;
  onRecorded: (audio: Blob, seconds: number) => void;
  onLimit: () => void;
}) {
  const [state, setState] = useState<RecorderState>("idle"),
    [elapsed, setElapsed] = useState(0),
    [error, setError] = useState("");
  const recorder = useRef<MediaRecorder | null>(null),
    stream = useRef<MediaStream | null>(null),
    chunks = useRef<Blob[]>([]),
    startedAt = useRef(0),
    ticker = useRef(0),
    limit = useRef(0),
    discard = useRef(false),
    mounted = useRef(true);
  const callbacks = useRef({ onRecorded, onLimit });
  useEffect(() => {
    callbacks.current = { onRecorded, onLimit };
  });
  const release = useCallback(() => {
    window.clearInterval(ticker.current);
    window.clearTimeout(limit.current);
    stream.current?.getTracks().forEach((track) => track.stop());
    stream.current = null;
    recorder.current = null;
  }, []);
  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
      discard.current = true;
      if (recorder.current?.state === "recording") recorder.current.stop();
      release();
    };
  }, [release]);
  const stop = useCallback(() => {
    if (recorder.current?.state === "recording") recorder.current.stop();
  }, []);
  const cancel = useCallback(() => {
    discard.current = true;
    stop();
  }, [stop]);
  // getUserMedia must run from the click: an effect would prompt twice under StrictMode.
  async function start() {
    if (state !== "idle") return;
    setError("");
    setState("starting");
    let media: MediaStream;
    try {
      media = await navigator.mediaDevices.getUserMedia({
        audio: {
          channelCount: 1,
          echoCancellation: true,
          noiseSuppression: true,
        },
      });
    } catch (e) {
      if (mounted.current) {
        setState("idle");
        setError(microphoneError(e));
      }
      return;
    }
    if (!mounted.current) {
      media.getTracks().forEach((track) => track.stop());
      return;
    }
    let rec: MediaRecorder;
    try {
      const mimeType = MIME_TYPES.find((type) =>
        MediaRecorder.isTypeSupported?.(type),
      );
      rec = new MediaRecorder(media, {
        ...(mimeType ? { mimeType } : {}),
        audioBitsPerSecond: 32000,
      });
    } catch (e) {
      media.getTracks().forEach((track) => track.stop());
      setState("idle");
      setError(microphoneError(e));
      return;
    }
    stream.current = media;
    recorder.current = rec;
    chunks.current = [];
    discard.current = false;
    rec.ondataavailable = (e) => {
      if (e.data.size) chunks.current.push(e.data);
    };
    rec.onstop = () => {
      const seconds = (performance.now() - startedAt.current) / 1000;
      const audio = new Blob(chunks.current, {
        type: rec.mimeType || chunks.current[0]?.type || "audio/webm",
      });
      chunks.current = [];
      release();
      if (!mounted.current) return;
      setState("idle");
      if (!discard.current) callbacks.current.onRecorded(audio, seconds);
    };
    rec.onerror = () => {
      discard.current = true;
      if (mounted.current) setError("L’enregistrement a été interrompu.");
      if (rec.state === "recording") rec.stop();
      else {
        release();
        if (mounted.current) setState("idle");
      }
    };
    // The microphone can disappear (unplugged, page sent to the background on iOS).
    media.getAudioTracks().forEach((track) => {
      track.onended = () => {
        if (rec.state === "recording") rec.stop();
      };
    });
    rec.start();
    startedAt.current = performance.now();
    setElapsed(0);
    setState("recording");
    ticker.current = window.setInterval(
      () =>
        setElapsed(Math.floor((performance.now() - startedAt.current) / 1000)),
      250,
    );
    limit.current = window.setTimeout(() => {
      callbacks.current.onLimit();
      stop();
    }, maxSeconds * 1000);
  }
  return { state, elapsed, error, setError, start, stop, cancel };
}
