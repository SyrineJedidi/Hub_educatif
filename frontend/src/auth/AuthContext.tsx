import { createContext, useContext, useEffect, useState } from "react";
import type { ReactNode } from "react";
import type { User } from "../api/types";
import { api, ApiError } from "../api/client";
interface Auth {
  user: User | null;
  loading: boolean;
  error: string;
  setUser: (user: User | null) => void;
  refresh: () => Promise<void>;
  logout: () => Promise<void>;
}
const Context = createContext<Auth>(null!);
export const destination = (user: User) =>
  user.role === "ADMIN"
    ? "/administration"
    : user.role === "TEACHER"
      ? "/espace/enseignant"
      : "/espace/etudiant";
export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null),
    [loading, setLoading] = useState(true),
    [error, setError] = useState("");
  async function refresh() {
    setError("");
    try {
      setUser((await api<{ user: User }>("auth/me/")).user);
    } catch (e) {
      setUser(null);
      if (!(e instanceof ApiError) || e.status !== 401)
        setError(e instanceof Error ? e.message : "Serveur indisponible.");
    } finally {
      setLoading(false);
    }
  }
  useEffect(() => {
    void refresh();
    const expired = () => setUser(null);
    window.addEventListener("session-expired", expired);
    return () => window.removeEventListener("session-expired", expired);
  }, []);
  async function logout() {
    await api("auth/logout/", "POST", {});
    setUser(null);
    window.location.assign("/");
  }
  return (
    <Context.Provider
      value={{ user, setUser, loading, error, refresh, logout }}
    >
      {children}
    </Context.Provider>
  );
}
export const useAuth = () => useContext(Context);
