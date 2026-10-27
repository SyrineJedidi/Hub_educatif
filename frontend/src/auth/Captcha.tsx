import { useCallback, useEffect, useRef, useState } from "react";
import type { DetailedHTMLProps, HTMLAttributes } from "react";
import { api } from "../api/client";

/**
 * ALTCHA: the browser solves a small proof of work issued and signed by our server, without any
 * puzzle for people (WCAG 2.2, criterion 3.3.8) and without any third-party service. The solution
 * is sent in the X-Captcha-Token header. When the server turns the check off, nothing is shown.
 */
type AuthConfig = { captcha: { enabled: boolean; provider: string }; email_verification: boolean };
type AltchaElement = HTMLElement & { reset?: () => void; verify?: () => void };
type AltchaState = { state: "verified" | "verifying" | "unverified" | "expired" | "error" | "code"; payload?: string };
declare module "react" {
  // eslint-disable-next-line @typescript-eslint/no-namespace
  namespace JSX {
    interface IntrinsicElements {
      "altcha-widget": DetailedHTMLProps<HTMLAttributes<HTMLElement>, HTMLElement> & {
        challenge?: string;
        auto?: string;
        language?: string;
        name?: string;
        configuration?: string;
      };
    }
  }
}
let config: Promise<AuthConfig> | null = null;
let widget: Promise<unknown> | null = null;

export const authConfig = () =>
  (config ??= api<AuthConfig>("auth/config/").catch((error) => {
    config = null;
    throw error;
  }));

// The widget code (with its French texts) is downloaded only on the pages that use it.
const loadWidget = () => (widget ??= import("altcha").then(() => import("altcha/i18n/fr-fr")));

export function useCaptcha(action: "login" | "register" | "reset" | "verify") {
  const box = useRef<AltchaElement>(null);
  const [enabled, setEnabled] = useState(false);
  const [token, setToken] = useState("");
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    let active = true;
    authConfig()
      .then(async ({ captcha }) => {
        if (!active || !captcha.enabled) return;
        await loadWidget();
        if (active) setEnabled(true);
      })
      .catch(() => active && setFailed(true));
    return () => {
      active = false;
    };
  }, []);
  useEffect(() => {
    const element = box.current;
    if (!enabled || !element) return;
    const onState = (event: Event) => {
      const { state, payload } = (event as CustomEvent<AltchaState>).detail;
      setToken(state === "verified" && payload ? payload : "");
      setFailed(state === "error");
      // An expired challenge is replaced at once, so the form never waits on the person.
      if (state === "expired") element.verify?.();
    };
    element.addEventListener("statechange", onState);
    return () => element.removeEventListener("statechange", onState);
  }, [enabled]);
  // A solution works once: a new challenge is solved after every submission.
  const reset = useCallback(() => {
    setToken("");
    box.current?.reset?.();
    box.current?.verify?.();
  }, []);
  const headers = useCallback((): Record<string, string> => {
    if (!enabled) return {};
    if (!token)
      throw new Error(
        failed
          ? "La vérification anti-robot a échoué. Rechargez la page puis réessayez."
          : "Vérification anti-robot en cours… Patientez une seconde puis réessayez.",
      );
    return { "X-Captcha-Token": token };
  }, [enabled, token, failed]);
  const element = enabled ? (
    <altcha-widget
      ref={box}
      className="captcha-box"
      challenge={`/api/auth/captcha/?action=${action}`}
      auto="onload"
      language="fr-fr"
      name="altcha"
      configuration={JSON.stringify({ hideFooter: true })}
    />
  ) : null;
  return { element, headers, reset, enabled };
}
