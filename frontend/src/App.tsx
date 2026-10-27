import {
  QuizManagerRoute,
  QuizModuleEntry,
  QuizStudentRoute,
} from "./quizzes/QuizRoutes";
import ManagementLayout from "./layouts/backoffice/ManagementLayout";
import { SheetModuleEntry, SheetManagerRoute } from "./revisions/routes";
import { lazy, Suspense, useEffect, useRef, useLayoutEffect } from "react";
import { Loading } from "./components/UI";
import {
  AssistantManagerRoute,
  AssistantModuleEntry,
  AssistantUserRoute,
} from "./assistant/AssistantRoutes";
import { setQuizLanguageScope, useQuizLanguage } from "./quizzes/i18n";
import { CourseManagerRoute, CourseModuleEntry } from "./courses/CourseRoutes";
import {
  PlanningCoachRoute,
  PlanningModuleEntry,
  PlanningStudentRoute,
} from "./planning/PlanningRoutes";
import { Routes, Route, useLocation, Navigate } from "react-router-dom";
import FrontOfficeLayout from "./layouts/front/FrontOfficeLayout";
import ProtectedLearningLayout from "./layouts/front/ProtectedLearningLayout";
import AdminLayout from "./layouts/backoffice/AdminLayout";
import Home from "./pages/Home";
import { ComingSoon, NotFound } from "./pages/Other";
import { useAuth, destination } from "./auth/AuthContext";
// Pages are loaded on demand: each one is a separate file downloaded at first visit.
const QuizList = lazy(() => import("./quizzes/QuizList"));
const QuizDetail = lazy(() => import("./quizzes/QuizDetail"));
const QuizEditor = lazy(() => import("./quizzes/QuizEditor"));
const QuestionEditor = lazy(() => import("./quizzes/QuestionEditor"));
const GenerateQuestions = lazy(() => import("./quizzes/GenerateQuestions"));
const QuizPreview = lazy(() => import("./quizzes/QuizPreview"));
const AttemptPage = lazy(() => import("./quizzes/AttemptPage"));
const AttemptResult = lazy(() => import("./quizzes/AttemptResult"));
const StudentAttempts = lazy(() => import("./quizzes/StudentAttempts"));
const StudentResults = lazy(() => import("./quizzes/StudentResults"));
const StudentResultDetail = lazy(() => import("./quizzes/StudentResultDetail"));
const SheetList = lazy(() => import("./revisions/pages/SheetList"));
const SheetDetail = lazy(() => import("./revisions/pages/SheetDetail"));
const SheetEditor = lazy(() => import("./revisions/pages/SheetEditor"));
const AIDashboard = lazy(() => import("./revisions/pages/AIDashboard"));
const SheetTable = lazy(() => import("./revisions/pages/SheetTable"));
const ModuleOverview = lazy(() => import("./revisions/pages/ModuleOverview"));
const AIWorkshop = lazy(() => import("./revisions/pages/AIWorkshop"));
const IllustrationLibrary = lazy(() => import("./revisions/pages/IllustrationLibrary"));
const JobJournal = lazy(() => import("./revisions/pages/JobJournal"));
const RevisionMode = lazy(() => import("./revisions/pages/RevisionMode"));
const StudentFollowUp = lazy(() => import("./revisions/pages/StudentFollowUp"));
const RolesPermissions = lazy(() => import("./pages/RolesPermissions"));
const PlanningDashboard = lazy(() => import("./planning/PlanningDashboard"));
const ObjectivesPage = lazy(() => import("./planning/ObjectivesPage"));
const AvailabilityPage = lazy(() => import("./planning/AvailabilityPage"));
const PlansPage = lazy(() => import("./planning/PlansPage"));
const PlanDetail = lazy(() => import("./planning/PlanDetail"));
const CoachStudents = lazy(() => import("./planning/CoachStudents"));
const CoachStudentDetail = lazy(() => import("./planning/CoachStudentDetail"));
const CourseList = lazy(() => import("./courses/CourseList"));
const CourseDetail = lazy(() => import("./courses/CourseDetail"));
const CourseEditor = lazy(() => import("./courses/CourseEditor"));
const CourseSearch = lazy(() => import("./courses/CourseSearch"));
const CourseStatistics = lazy(() => import("./courses/CourseStatistics"));
const ResourceViewer = lazy(() => import("./courses/ResourceViewer"));
const SubjectList = lazy(() => import("./courses/SubjectList"));
const AssistantPage = lazy(() => import("./assistant/AssistantPage"));
const NotesPage = lazy(() => import("./assistant/NotesPage"));
const SettingsPage = lazy(() => import("./assistant/SettingsPage"));
const InsightsPage = lazy(() => import("./assistant/InsightsPage"));
const ReviewQueue = lazy(() => import("./assistant/ReviewQueue"));
const ReviewDetail = lazy(() => import("./assistant/ReviewDetail"));
const AdminUsage = lazy(() => import("./assistant/AdminUsage"));
const LearningHome = lazy(() => import("./pages/LearningHome"));
const AuthPage = lazy(() => import("./pages/AuthPages"));
const VerifyEmail = lazy(() => import("./pages/VerifyEmail"));
const Dashboard = lazy(() => import("./pages/Dashboard"));
const Users = lazy(() => import("./pages/Users"));
const Groups = lazy(() => import("./pages/Groups"));
const GroupDetail = lazy(() => import("./pages/GroupDetail"));
const Sessions = lazy(() => import("./pages/Sessions"));
const SessionDetail = lazy(() => import("./pages/SessionDetail"));
const Attendance = lazy(() => import("./pages/Attendance"));
const Profile = lazy(() => import("./pages/Profile"));
const Statistics = lazy(() => import("./pages/Statistics"));
function WorkspaceIndex() {
  const { user } = useAuth();
  return user ? <Navigate to={destination(user)} replace /> : null;
}
export default function App() {
  const { pathname } = useLocation();
  // The interface language chosen in the quiz module applies to its pages only.
  const quizPage = /\/(quiz|resultats-quiz)(\/|$)/.test(pathname);
  setQuizLanguageScope(quizPage);
  const language = useQuizLanguage();
  useLayoutEffect(() => {
    document.documentElement.lang = language;
    // The back-office template (Soft UI) has no right-to-left layout.
    const backOffice = /^\/(administration|gestion)(\/|$)/.test(pathname);
    document.documentElement.dir = language === "ar" && !backOffice ? "rtl" : "ltr";
  }, [language, pathname]);
  const previousPath = useRef(pathname);
  useEffect(() => {
    window.scrollTo(0, 0);
    document.title = "Hub Éducatif Multimodal — Nexora";
    if (previousPath.current !== pathname)
      document.getElementById("main")?.focus();
    previousPath.current = pathname;
  }, [pathname]);
  return (
    <Suspense fallback={<Loading />}>
    <Routes>
      <Route element={<FrontOfficeLayout />}>
        <Route index element={<Home />} />
        <Route path="connexion" element={<AuthPage mode="login" />} />
        <Route path="inscription" element={<AuthPage mode="register" />} />
        <Route path="verifier-email" element={<VerifyEmail />} />
        <Route
          path="mot-de-passe-oublie"
          element={<AuthPage mode="forgot" />}
        />
        <Route
          path="reinitialiser-mot-de-passe"
          element={<AuthPage mode="reset" />}
        />
        <Route path="modules/quiz" element={<QuizModuleEntry />} />
        <Route path="modules/resumes" element={<SheetModuleEntry />} />
        <Route path="modules/assistant" element={<AssistantModuleEntry />} />
        <Route path="modules/cours" element={<CourseModuleEntry />} />
        <Route path="modules/coaching" element={<PlanningModuleEntry />} />
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
            <Route path="quiz/:id/generer" element={<GenerateQuestions />} />
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
          <Route path="fiches" element={<SheetList />} />
          <Route path="fiches/nouvelle" element={<SheetEditor />} />
          <Route path="fiches/atelier-ia" element={<AIWorkshop />} />
          <Route element={<SheetManagerRoute />}>
            <Route
              path="fiches/pilotage-ia"
              element={<Navigate to="/gestion/statistiques-ia" replace />}
            />
          </Route>
          <Route path="fiches/:id" element={<SheetDetail />} />
          <Route path="fiches/:id/modifier" element={<SheetEditor />} />
          <Route path="fiches/:id/reviser" element={<RevisionMode />} />
          <Route path="modules/resumes" element={<SheetModuleEntry />} />
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
          <Route path="cours" element={<CourseList />} />
          <Route path="cours/recherche" element={<CourseSearch />} />
          <Route path="cours/:id" element={<CourseDetail />} />
          <Route
            path="cours/:id/ressources/:resourceId"
            element={<ResourceViewer />}
          />
          <Route path="modules/cours" element={<CourseModuleEntry />} />
          <Route element={<CourseManagerRoute />}>
            <Route path="cours/nouveau" element={<CourseEditor />} />
            <Route path="cours/:id/modifier" element={<CourseEditor />} />
            <Route
              path="cours/:id/statistiques"
              element={<CourseStatistics />}
            />
            <Route path="matieres" element={<SubjectList />} />
          </Route>
          <Route path="modules/coaching" element={<PlanningModuleEntry />} />
          <Route element={<PlanningStudentRoute />}>
            <Route path="planning" element={<PlanningDashboard />} />
            <Route path="planning/objectifs" element={<ObjectivesPage />} />
            <Route
              path="planning/disponibilites"
              element={<AvailabilityPage />}
            />
            <Route path="planning/plannings" element={<PlansPage />} />
            <Route path="planning/plannings/:id" element={<PlanDetail />} />
          </Route>
          <Route element={<PlanningCoachRoute />}>
            <Route path="suivi-revisions" element={<CoachStudents />} />
            <Route
              path="suivi-revisions/:studentId"
              element={<CoachStudentDetail />}
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
      <Route path="gestion" element={<ManagementLayout />}>
        <Route index element={<ModuleOverview />} />
        <Route path="fiches" element={<SheetTable />} />
        <Route path="fiches/nouvelle" element={<SheetEditor />} />
        <Route path="fiches/:id" element={<SheetDetail />} />
        <Route path="fiches/:id/modifier" element={<SheetEditor />} />
        <Route path="fiches/:id/reviser" element={<RevisionMode />} />
        <Route path="atelier-ia" element={<AIWorkshop />} />
        <Route path="illustrations" element={<IllustrationLibrary />} />
        <Route path="journal-ia" element={<JobJournal />} />
        <Route path="statistiques-ia" element={<AIDashboard />} />
        <Route path="suivi-etudiants" element={<StudentFollowUp />} />
        <Route path="droits" element={<RolesPermissions />} />
        <Route path="*" element={<NotFound />} />
      </Route>
      <Route path="administration" element={<AdminLayout />}>
        <Route index element={<Dashboard />} />
        <Route path="utilisateurs" element={<Users />} />
        <Route path="quiz" element={<QuizList />} />
        <Route path="quiz/:id" element={<QuizDetail />} />
        <Route path="modules/quiz" element={<QuizModuleEntry />} />
        <Route element={<QuizManagerRoute />}>
          <Route path="quiz/:id/generer" element={<GenerateQuestions />} />
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
        <Route path="resumes" element={<ModuleOverview />} />
        <Route path="fiches" element={<SheetTable />} />
        <Route path="fiches/nouvelle" element={<SheetEditor />} />
        <Route path="atelier-ia" element={<AIWorkshop />} />
        <Route path="illustrations" element={<IllustrationLibrary />} />
        <Route path="journal-ia" element={<JobJournal />} />
        <Route path="suivi-etudiants" element={<StudentFollowUp />} />
        <Route path="roles" element={<RolesPermissions />} />
        <Route path="pilotage-ia" element={<AIDashboard />} />
        <Route path="fiches/:id" element={<SheetDetail />} />
        <Route path="fiches/:id/modifier" element={<SheetEditor />} />
        <Route path="modules/resumes" element={<SheetModuleEntry />} />
        <Route path="assistant" element={<AdminUsage />} />
        <Route path="assistant/notes" element={<NotesPage />} />
        <Route path="assistant/parametres" element={<SettingsPage />} />
        <Route path="assistant/suivi" element={<InsightsPage />} />
        <Route path="assistant/signalements" element={<ReviewQueue />} />
        <Route path="assistant/signalements/:id" element={<ReviewDetail />} />
        <Route path="modules/assistant" element={<AssistantModuleEntry />} />
        <Route path="cours" element={<CourseList />} />
        <Route path="cours/recherche" element={<CourseSearch />} />
        <Route path="cours/:id" element={<CourseDetail />} />
        <Route
          path="cours/:id/ressources/:resourceId"
          element={<ResourceViewer />}
        />
        <Route path="modules/cours" element={<CourseModuleEntry />} />
        <Route element={<CourseManagerRoute />}>
          <Route path="cours/nouveau" element={<CourseEditor />} />
          <Route path="cours/:id/modifier" element={<CourseEditor />} />
          <Route path="cours/:id/statistiques" element={<CourseStatistics />} />
          <Route path="matieres" element={<SubjectList />} />
        </Route>
        <Route path="modules/coaching" element={<PlanningModuleEntry />} />
        <Route element={<PlanningCoachRoute />}>
          <Route path="suivi-revisions" element={<CoachStudents />} />
          <Route
            path="suivi-revisions/:studentId"
            element={<CoachStudentDetail />}
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
    </Routes>
    </Suspense>
  );
}
