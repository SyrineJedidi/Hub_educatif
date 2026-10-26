import { useAuth } from "../auth/AuthContext";
export function useAssistantContext() {
  const { user } = useAuth();
  const admin = user?.role === "ADMIN",
    student = user?.role === "STUDENT";
  return {
    user,
    admin,
    student,
    teacher: user?.role === "TEACHER",
    base: admin ? "/administration/assistant" : "/espace/assistant",
    chat: "/espace/assistant",
  };
}
