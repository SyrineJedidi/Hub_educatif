import { Navigate, Outlet } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { Loading } from "../components/UI";
import { useQuizContext } from "./useQuizContext";
export function QuizManagerRoute() {
  const { student, base } = useQuizContext();
  return student ? <Navigate to={base} replace /> : <Outlet />;
}
export function QuizStudentRoute() {
  const { student, base } = useQuizContext();
  return student ? <Outlet /> : <Navigate to={base} replace />;
}
export function QuizModuleEntry() {
  const { user, loading } = useAuth();
  if (loading) return <Loading />;
  return (
    <Navigate
      to={
        user
          ? user.role === "ADMIN"
            ? "/administration/quiz"
            : "/espace/quiz"
          : "/connexion"
      }
      replace
    />
  );
}
