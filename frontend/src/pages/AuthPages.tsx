import { Link, useNavigate, useSearchParams, Navigate } from "react-router-dom";
import { api } from "../api/client";
import { useAuth, destination } from "../auth/AuthContext";
import type { User } from "../api/types";
import { Field, Select, Form, val, Loading } from "../components/UI";
const titles = {
  login: "Heureux de vous retrouver",
  register: "Votre parcours commence ici",
  forgot: "Retrouvons votre accès",
  reset: "Un nouveau départ",
};
export default function AuthPage({ mode }: { mode: keyof typeof titles }) {
  const { user, setUser, loading } = useAuth(),
    navigate = useNavigate();
  const [params] = useSearchParams();
  if (loading) return <Loading />;
  if (user && (mode === "login" || mode === "register"))
    return <Navigate to={destination(user)} replace />;
  async function submit(form: FormData) {
    const email = val(form, "email");
    const password = val(form, "password"),
      confirmation = val(form, "confirmation");
    if ((mode === "register" || mode === "reset") && password !== confirmation)
      throw new Error("Les mots de passe ne correspondent pas.");
    if (mode === "login") {
      const result = await api<{ user: User }>("auth/login/", "POST", {
        email,
        password,
      });
      setUser(result.user);
      navigate(destination(result.user), { replace: true });
    }
    if (mode === "register") {
      await api("auth/register/", "POST", {
        email,
        password,
        confirmation,
        role: val(form, "role"),
        first_name: val(form, "first_name"),
        last_name: val(form, "last_name"),
      });
      navigate("/connexion?inscription=ok");
    }
    if (mode === "forgot") await api("auth/password/reset/", "POST", { email });
    if (mode === "reset") {
      await api("auth/password/confirm/", "POST", {
        token: params.get("token") || "",
        password,
        confirmation,
      });
      setUser(null);
      navigate("/connexion?reinitialisation=ok");
    }
  }
  return (
    <section className="auth-section">
      <div className="container">
        <div className="row align-items-center">
          <div className="col-lg-6 auth-illustration">
            <p className="eyebrow">HUB ÉDUCATIF MULTIMODAL</p>
            <h1>
              Apprendre.
              <br />
              Partager.
              <br />
              <span>Avancer ensemble.</span>
            </h1>
            <ul className="auth-visual" aria-hidden="true">
              <li className="tone-emerald">
                <span className="ti-book" /> <strong>Fiche prête</strong> La photosynthèse
              </li>
              <li className="tone-amber">
                <span className="ti-cup" /> <strong>Quiz réussi</strong> 6 / 6 bonnes réponses
              </li>
              <li className="tone-apricot">
                <span className="ti-calendar" /> <strong>Séance demain</strong> Biologie · 9 h 00
              </li>
            </ul>
          </div>
          <div className="col-lg-6">
            <div className="auth-card">
              <p className="eyebrow">VOTRE ESPACE NEXORA</p>
              <h2>{titles[mode]}</h2>
              <p className="intro">
                {mode === "register"
                  ? "Étudiant ou enseignant, choisissez votre rôle pour rejoindre le Hub."
                  : mode === "forgot"
                    ? "Saisissez votre email. Si un compte correspond, vous recevrez un lien valable une heure."
                    : "Vos groupes, vos séances et votre suivi vous attendent."}
              </p>
              {params.has("inscription") && (
                <p className="notice" role="status">
                  Compte créé. Vous pouvez vous connecter.
                </p>
              )}
              {params.has("reinitialisation") && (
                <p className="notice" role="status">
                  Mot de passe réinitialisé. Reconnectez-vous.
                </p>
              )}
              <Form
                key={mode}
                onSubmit={submit}
                label={
                  mode === "login"
                    ? "Se connecter ↗"
                    : mode === "register"
                      ? "Créer mon compte ↗"
                      : mode === "forgot"
                        ? "Envoyer le lien"
                        : "Réinitialiser le mot de passe"
                }
              >
                {mode === "register" && (
                  <div className="form-grid">
                    <Field
                      name="first_name"
                      label="Prénom"
                      required
                      maxLength={100}
                      autoComplete="given-name"
                    />
                    <Field
                      name="last_name"
                      label="Nom"
                      required
                      maxLength={100}
                      autoComplete="family-name"
                    />
                  </div>
                )}
                {mode === "register" && (
                  <Select name="role" label="Je suis" defaultValue="" required>
                    <option value="" disabled>
                      Choisir mon rôle
                    </option>
                    <option value="STUDENT">Étudiant</option>
                    <option value="TEACHER">Enseignant</option>
                  </Select>
                )}
                {mode !== "reset" && (
                  <Field
                    name="email"
                    label="Adresse email"
                    type="email"
                    autoComplete="email"
                    required
                    maxLength={254}
                  />
                )}{" "}
                {mode !== "forgot" && (
                  <Field
                    name="password"
                    label="Mot de passe"
                    type="password"
                    autoComplete={
                      mode === "login" ? "current-password" : "new-password"
                    }
                    minLength={mode === "login" ? 1 : 10}
                    maxLength={128}
                    required
                  />
                )}
                {(mode === "register" || mode === "reset") && (
                  <>
                    <p className="field-help">
                      Au moins 10 caractères ; évitez un mot de passe courant ou
                      uniquement numérique.
                    </p>
                    <Field
                      name="confirmation"
                      label="Confirmer le mot de passe"
                      type="password"
                      autoComplete="new-password"
                      required
                      minLength={10}
                      maxLength={128}
                    />
                  </>
                )}
              </Form>
              {mode === "forgot" && (
                <p className="field-help">
                  La réponse reste identique, que l’adresse corresponde ou non à
                  un compte.
                </p>
              )}
              <div className="auth-links">
                {mode === "login" ? (
                  <>
                    <Link to="/mot-de-passe-oublie">Mot de passe oublié ?</Link>
                    <p>
                      Vous découvrez le Hub ?{" "}
                      <Link to="/inscription">S’inscrire</Link>
                    </p>
                  </>
                ) : (
                  <Link to="/connexion">Revenir à la connexion</Link>
                )}
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
