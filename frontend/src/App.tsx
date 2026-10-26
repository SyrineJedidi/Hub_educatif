import QuizList from "./quizzes/QuizList";
import QuizDetail from "./quizzes/QuizDetail";
import QuizEditor from "./quizzes/QuizEditor";
import QuestionEditor from "./quizzes/QuestionEditor";
import QuizPreview from "./quizzes/QuizPreview";
import {
  QuizManagerRoute,
  QuizModuleEntry,
  QuizStudentRoute,
} from "./quizzes/QuizRoutes";
import AttemptPage from "./quizzes/AttemptPage";
import AttemptResult from "./quizzes/AttemptResult";
import StudentAttempts from "./quizzes/StudentAttempts";
import StudentResults from "./quizzes/StudentResults";
import StudentResultDetail from "./quizzes/StudentResultDetail";
import AssistantPage from "./assistant/AssistantPage";
import NotesPage from "./assistant/NotesPage";
import SettingsPage from "./assistant/SettingsPage";
import InsightsPage from "./assistant/InsightsPage";
import ReviewQueue from "./assistant/ReviewQueue";
import ReviewDetail from "./assistant/ReviewDetail";
import AdminUsage from "./assistant/AdminUsage";
import {
  AssistantManagerRoute,
  AssistantModuleEntry,
  AssistantUserRoute,
} from "./assistant/AssistantRoutes";
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
        <Route path="modules/quiz" element={<QuizModuleEntry />} />
        <Route path="modules/assistant" element={<AssistantModuleEntry />} />
        <Route path="modules/:slug" element={<ComingSoon />} />
        <Route path="*" element={<NotFound />} />
        <Route path="espace" element={<ProtectedLearningLayout />}>
          <Route index element={<WorkspaceIndex />} />
          <Route path="etudiant" element={<LearningHome />} />
          <Route path="enseignant" element={<LearningHome />} />
          <Route path="quiz" element={<QuizList />} />
          <Route path="quiz/:id" element={<QuizDetail />} />
          <Route element={<QuizStudentRoute />}>
            <Route path="tentatives" element={<StudentAttempts />} />
            <Route path="tentatives/:attemptId" element={<AttemptPage />} />
            <Route
              path="tentatives/:attemptId/resultat"
              element={<AttemptResult />}
            />
          </Route>
          <Route path="modules/quiz" element={<QuizModuleEntry />} />
          <Route element={<QuizManagerRoute />}>
            <Route path="quiz/:id/resultats" element={<StudentResults />} />
            <Route path="resultats-quiz" element={<StudentResults />} />
            <Route
              path="resultats-quiz/:attemptId"
              element={<StudentResultDetail />}
            />
            <Route path="quiz/nouveau" element={<QuizEditor />} />
            <Route path="quiz/:id/modifier" element={<QuizEditor />} />
            <Route
              path="quiz/:id/dupliquer"
              element={<QuizEditor duplicate />}
            />
            <Route
              path="quiz/:id/questions/nouvelle"
              element={<QuestionEditor />}
            />
            <Route
              path="quiz/:id/questions/:questionId/modifier"
              element={<QuestionEditor />}
            />
            <Route path="quiz/:id/previsualisation" element={<QuizPreview />} />
          </Route>
          <Route path="modules/assistant" element={<AssistantModuleEntry />} />
          <Route element={<AssistantUserRoute />}>
            <Route path="assistant" element={<AssistantPage />} />
          </Route>
          <Route element={<AssistantManagerRoute />}>
            <Route path="assistant/notes" element={<NotesPage />} />
            <Route path="assistant/parametres" element={<SettingsPage />} />
            <Route path="assistant/suivi" element={<InsightsPage />} />
            <Route path="assistant/signalements" element={<ReviewQueue />} />
            <Route
              path="assistant/signalements/:id"
              element={<ReviewDetail />}
            />
          </Route>
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
        <Route path="quiz" element={<QuizList />} />
        <Route path="quiz/:id" element={<QuizDetail />} />
        <Route path="modules/quiz" element={<QuizModuleEntry />} />
        <Route element={<QuizManagerRoute />}>
          <Route path="quiz/:id/resultats" element={<StudentResults />} />
          <Route path="resultats-quiz" element={<StudentResults />} />
          <Route
            path="resultats-quiz/:attemptId"
            element={<StudentResultDetail />}
          />
          <Route path="quiz/nouveau" element={<QuizEditor />} />
          <Route path="quiz/:id/modifier" element={<QuizEditor />} />
          <Route path="quiz/:id/dupliquer" element={<QuizEditor duplicate />} />
          <Route
            path="quiz/:id/questions/nouvelle"
            element={<QuestionEditor />}
          />
          <Route
            path="quiz/:id/questions/:questionId/modifier"
            element={<QuestionEditor />}
          />
          <Route path="quiz/:id/previsualisation" element={<QuizPreview />} />
        </Route>
        <Route path="assistant" element={<AdminUsage />} />
        <Route path="assistant/notes" element={<NotesPage />} />
        <Route path="assistant/parametres" element={<SettingsPage />} />
        <Route path="assistant/suivi" element={<InsightsPage />} />
        <Route path="assistant/signalements" element={<ReviewQueue />} />
        <Route path="assistant/signalements/:id" element={<ReviewDetail />} />
        <Route path="modules/assistant" element={<AssistantModuleEntry />} />
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
