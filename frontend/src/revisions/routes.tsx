import { Navigate, Outlet } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { Loading } from "../components/UI";
import { modulePaths } from "./hooks/useSheetContext";
export function SheetModuleEntry() {
  const { user, loading } = useAuth();
  if (loading) return <Loading />;
  return (
    <Navigate
      to={
        user ? modulePaths(user.role).home : "/connexion"
      }
      replace
    />
  );
}
export function SheetManagerRoute() {
  const { user } = useAuth();
  return user?.role === "STUDENT" ? (
    <Navigate to="/espace/fiches" replace />
  ) : (
    <Outlet />
  );
}
