import { useAuth } from "../auth/AuthContext";
import { api } from "../api/client";
import { Field, Form, val, statuses } from "../components/UI";
import type { User } from "../api/types";
import { useNavigate } from "react-router-dom";
export default function Profile() {
  const { user, setUser } = useAuth(),
    navigate = useNavigate();
  return (
    <>
      <div className="page-heading">
        <div>
          <p className="eyebrow">VOTRE ESPACE PERSONNEL</p>
          <h1>Mon profil</h1>
          <p>Les informations qui vous accompagnent dans le Hub.</p>
        </div>
      </div>
      <div className="dashboard-columns">
        <section className="panel">
          <h2>Informations personnelles</h2>
          <Form
            onSubmit={async (f) => {
              const d = await api<{ user: User }>("profile/", "PATCH", {
                first_name: val(f, "first_name"),
                last_name: val(f, "last_name"),
              });
              setUser(d.user);
            }}
          >
            <div className="form-grid">
              <Field
                label="Prénom"
                name="first_name"
                defaultValue={user!.first_name}
                required
                maxLength={100}
              />
              <Field
                label="Nom"
                name="last_name"
                defaultValue={user!.last_name}
                required
                maxLength={100}
              />
            </div>
            <Field
              label="Email (lecture seule, adresse non vérifiée)"
              value={user!.email}
              readOnly
            />
            <Field
              label="Rôle (lecture seule)"
              value={statuses[user!.role]}
              readOnly
            />
          </Form>
          <hr />
          <h2>Mon avatar</h2>
          <Form
            label="Mettre à jour l’avatar"
            onSubmit={async (f) => {
              const d = await api<{ user: User }>("profile/avatar/", "POST", f);
              setUser({
                ...d.user,
                avatar: d.user.avatar + "?v=" + Date.now(),
              });
            }}
          >
            <Field
              label="Image PNG, JPEG ou WebP · 2 Mo maximum"
              name="avatar"
              type="file"
              accept="image/png,image/jpeg,image/webp"
              required
            />
          </Form>
          {user!.avatar && (
            <Form
              label="Retirer l’avatar"
              onSubmit={async () => {
                const d = await api<{ user: User }>(
                  "profile/avatar/",
                  "DELETE",
                );
                setUser(d.user);
              }}
            />
          )}
        </section>
        <section className="panel">
          <h2>Changer mon mot de passe</h2>
          <p className="intro">
            Vous serez déconnecté de tous vos appareils après le changement.
          </p>
          <Form
            label="Modifier le mot de passe"
            onSuccess={() => {
              setUser(null);
              navigate("/connexion?reinitialisation=ok");
            }}
            onSubmit={(f) => {
              if (val(f, "password") !== val(f, "confirmation"))
                throw new Error("Les mots de passe ne correspondent pas.");
              return api("auth/password/change/", "POST", {
                old_password: val(f, "old_password"),
                password: val(f, "password"),
                confirmation: val(f, "confirmation"),
              });
            }}
          >
            <Field
              name="old_password"
              label="Ancien mot de passe"
              type="password"
              autoComplete="current-password"
              required
            />
            <Field
              name="password"
              label="Nouveau mot de passe"
              type="password"
              autoComplete="new-password"
              required
              minLength={10}
              maxLength={128}
            />
            <Field
              name="confirmation"
              label="Confirmer le nouveau mot de passe"
              type="password"
              autoComplete="new-password"
              required
              minLength={10}
              maxLength={128}
            />
          </Form>
        </section>
      </div>
    </>
  );
}
