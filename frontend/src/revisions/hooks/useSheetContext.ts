import { useLocation } from "react-router-dom";
import { useAuth } from "../../auth/AuthContext";
export function useSheetContext() {
  const { user } = useAuth();
  const { pathname } = useLocation();
  const admin = user?.role === "ADMIN",
    student = user?.role === "STUDENT",
    teacher = user?.role === "TEACHER";
  // Teachers manage their sheets in the /gestion back-office and read them in /espace.
  const managing = admin || pathname.startsWith("/gestion");
  return {
    user,
    admin,
    student,
    teacher,
    managing,
    base: admin
      ? "/administration/fiches"
      : managing
        ? "/gestion/fiches"
        : "/espace/fiches",
    paths: modulePaths(user?.role),
  };
}
/** Every page of the module, for the role of the connected user. */
export function modulePaths(role?: string) {
  if (role === "ADMIN")
    return {
      home: "/administration/resumes",
      sheets: "/administration/fiches",
      workshop: "/administration/atelier-ia",
      library: "/administration/illustrations",
      journal: "/administration/journal-ia",
      stats: "/administration/pilotage-ia",
      followUp: "/administration/suivi-etudiants",
      reading: "/administration/fiches",
    };
  if (role === "TEACHER")
    return {
      home: "/gestion",
      sheets: "/gestion/fiches",
      workshop: "/gestion/atelier-ia",
      library: "/gestion/illustrations",
      journal: "/gestion/journal-ia",
      stats: "/gestion/statistiques-ia",
      followUp: "/gestion/suivi-etudiants",
      reading: "/espace/fiches",
    };
  return {
    home: "/espace/fiches",
    sheets: "/espace/fiches",
    workshop: "/espace/fiches/atelier-ia",
    library: "",
    journal: "",
    stats: "",
    followUp: "",
    reading: "/espace/fiches",
  };
}
