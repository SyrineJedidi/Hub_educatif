import { useAuth } from "../auth/AuthContext";
export function useCourseContext() {
  const { user } = useAuth();
  const admin = user?.role === "ADMIN",
    student = user?.role === "STUDENT";
  return {
    user,
    admin,
    student,
    base: admin ? "/administration/cours" : "/espace/cours",
    subjects: admin ? "/administration/matieres" : "/espace/matieres",
    apiBase: student ? "student/courses/" : "courses/",
  };
}
