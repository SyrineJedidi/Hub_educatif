import { useAuth } from "../auth/AuthContext";
import type { Role } from "../api/types";
export const planningHome = (role: Role) =>
  role === "ADMIN"
    ? "/administration/suivi-revisions"
    : role === "TEACHER"
      ? "/espace/suivi-revisions"
      : "/espace/planning";
export function usePlanningContext() {
  const { user } = useAuth();
  const admin = user?.role === "ADMIN",
    student = user?.role === "STUDENT";
  return {
    user,
    admin,
    student,
    base: "/espace/planning",
    coachBase: admin
      ? "/administration/suivi-revisions"
      : "/espace/suivi-revisions",
    apiBase: "student/planning/",
    coachApi: "planning/students/",
  };
}
