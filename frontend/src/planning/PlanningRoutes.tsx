import { Navigate, Outlet } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { Loading } from "../components/UI";
import { planningHome, usePlanningContext } from "./usePlanningContext";
export function PlanningStudentRoute() {
  const { user, student } = usePlanningContext();
  return student ? (
    <Outlet />
  ) : (
    <Navigate to={user ? planningHome(user.role) : "/connexion"} replace />
  );
}
export function PlanningCoachRoute() {
  const { student, base } = usePlanningContext();
  return student ? <Navigate to={base} replace /> : <Outlet />;
}
export function PlanningModuleEntry() {
  const { user, loading } = useAuth();
  if (loading) return <Loading />;
  return (
    <Navigate to={user ? planningHome(user.role) : "/connexion"} replace />
  );
}
