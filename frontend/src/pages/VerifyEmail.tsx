import { useEffect, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { api, ApiError } from "../api/client";

/** Target of the link sent after registration: confirms the address, then leads to the login page. */
export default function VerifyEmail() {
  const [params] = useSearchParams();
  const [state, setState] = useState<"pending" | "done" | "error">("pending");
  const [message, setMessage] = useState("");
  const sent = useRef(false);
  useEffect(() => {
    if (sent.current) return;
    sent.current = true;
    api<{ message: string }>("auth/email/verify/", "POST", { token: params.get("token") || "" })
      .then((result) => {
        setMessage(result.message);
        setState("done");
      })
      .catch((error) => {
        const field = error instanceof ApiError ? error.fields.token : undefined;
        setMessage(Array.isArray(field) ? field.join(" ") : error instanceof Error ? error.message : "La confirmation a échoué.");
        setState("error");
      });
  }, [params]);
  return (
    <section className="auth-section">
      <div className="container">
        <div className="auth-card verify-card">
          <p className="eyebrow">VOTRE ESPACE NEXORA</p>
          <h1>
            {state === "pending"
              ? "Confirmation de votre adresse…"
              : state === "done"
                ? "Adresse confirmée"
                : "Lien de confirmation inutilisable"}
          </h1>
          <p className={state === "error" ? "notice notice-error" : "notice"} role={state === "error" ? "alert" : "status"}>
            {state === "pending" ? "Un instant, nous vérifions votre lien." : message}
          </p>
          {state !== "pending" && (
            <Link className="btn_one" to={state === "done" ? "/connexion?verification=ok" : "/connexion"}>
              {state === "done" ? "Me connecter" : "Demander un nouvel email depuis la connexion"}
            </Link>
          )}
        </div>
      </div>
    </section>
  );
}
