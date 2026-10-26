import { useAuth } from "../auth/AuthContext";
export function useQuizContext() {
  const { user } = useAuth();
  const admin = user?.role === "ADMIN",
    student = user?.role === "STUDENT";
  return {
    user,
    admin,
    student,
    base: admin ? "/administration/quiz" : "/espace/quiz",
    apiBase: student ? "student/quizzes/" : "quizzes/",
  };
}
