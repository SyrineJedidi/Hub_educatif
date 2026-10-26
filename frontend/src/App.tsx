import { useEffect, useRef } from "react";
import { Routes, Route, useLocation, Navigate } from "react-router-dom";
import FrontOfficeLayout from "./layouts/FrontOfficeLayout";
import ProtectedLearningLayout from "./layouts/ProtectedLearningLayout";
import LearningHome from "./pages/LearningHome";
import AdminLayout from "./layouts/AdminLayout";
import Home from "./pages/Home";
import AuthPage from "./pages/AuthPages";
import Dashboard from "./pages/Dashboard";
import Users from "./pages/Users";
import Groups from "./pages/Groups";
import GroupDetail from "./pages/GroupDetail";
import Sessions from "./pages/Sessions";
import SessionDetail from "./pages/SessionDetail";
import Attendance from "./pages/Attendance";
import Profile from "./pages/Profile";
import Statistics from "./pages/Statistics";
import { ComingSoon, NotFound } from "./pages/Other";
import { useAuth, destination } from "./auth/AuthContext";
function WorkspaceIndex() {
  const { user } = useAuth();
  return user ? <Navigate to={destination(user)} replace /> : null;
}
export default function App() {
  const { pathname } = useLocation();
  const previousPath = useRef(pathname);
  useEffect(() => {
    window.scrollTo(0, 0);
    document.title = "Hub Éducatif Multimodal — Nexora";
    if (previousPath.current !== pathname)
      document.getElementById("main")?.focus();
    previousPath.current = pathname;
  }, [pathname]);
  return (
    <Routes>
      <Route element={<FrontOfficeLayout />}>
        <Route index element={<Home />} />
        <Route path="connexion" element={<AuthPage mode="login" />} />
        <Route path="inscription" element={<AuthPage mode="register" />} />
        <Route
          path="mot-de-passe-oublie"
          element={<AuthPage mode="forgot" />}
        />
        <Route
          path="reinitialiser-mot-de-passe"
          element={<AuthPage mode="reset" />}
        />
        <Route path="modules/:slug" element={<ComingSoon />} />
        <Route path="*" element={<NotFound />} />
        <Route path="espace" element={<ProtectedLearningLayout />}>
          <Route index element={<WorkspaceIndex />} />
          <Route path="etudiant" element={<LearningHome />} />
          <Route path="enseignant" element={<LearningHome />} />
          <Route path="profil" element={<Profile />} />
          <Route path="groupes" element={<Groups />} />
          <Route path="groupes/:id" element={<GroupDetail />} />
          <Route path="seances" element={<Sessions />} />
          <Route path="seances/:id" element={<SessionDetail />} />
          <Route path="seances/:id/appel" element={<Attendance />} />
          <Route path="assiduite" element={<Statistics />} />
          <Route path="modules/:slug" element={<ComingSoon />} />
          <Route path="*" element={<NotFound />} />
        </Route>
      </Route>
      <Route path="administration" element={<AdminLayout />}>
        <Route index element={<Dashboard />} />
        <Route path="utilisateurs" element={<Users />} />
        <Route path="profil" element={<Profile />} />
        <Route path="groupes" element={<Groups />} />
        <Route path="groupes/:id" element={<GroupDetail />} />
        <Route path="seances" element={<Sessions />} />
        <Route path="seances/:id" element={<SessionDetail />} />
        <Route path="seances/:id/appel" element={<Attendance />} />
        <Route path="assiduite" element={<Statistics />} />
        <Route path="modules/:slug" element={<ComingSoon />} />
        <Route path="*" element={<NotFound />} />
      </Route>
    </Routes>
  );
}
