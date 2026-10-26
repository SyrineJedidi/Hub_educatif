export type Role = "ADMIN" | "TEACHER" | "STUDENT";
export interface User {
  id: string;
  first_name: string;
  last_name: string;
  email: string;
  role: Role;
  is_active: boolean;
  avatar: string | null;
  date_joined: string;
  last_login: string | null;
}
export interface Page<T> {
  count: number;
  page: number;
  page_size: number;
  results: T[];
}
export interface Group {
  id: string;
  name: string;
  code: string;
  description: string;
  level: string;
  academic_year: string;
  teacher_id: string;
  teacher_name: string;
  archived: boolean;
}
export interface Enrollment {
  id: string;
  student_id: string;
  student_name: string;
  group_id: string;
  group_name: string;
  starts_at: string;
  ends_at: string | null;
}
export interface Session {
  id: string;
  group_id: string;
  group_name: string;
  title: string;
  description: string;
  starts_at: string;
  ends_at: string;
  location: string;
  status: "PLANNED" | "COMPLETED" | "CANCELLED";
}
export type AttendanceStatus =
  | "UNSET"
  | "PRESENT"
  | "LATE"
  | "ABSENT"
  | "EXCUSED";
export interface Entry {
  student_id: string;
  student_name: string;
  status: AttendanceStatus;
  comment: string;
}
export interface History {
  student_id: string;
  old_status: string;
  new_status: string;
  old_comment: string;
  new_comment: string;
  author_id: string;
  author_name?: string;
  at: string;
  reason: string;
  was_validated: boolean;
}
export interface Sheet {
  id: string;
  session_id: string;
  version: number;
  validated: boolean;
  entries: Entry[];
  history: History[];
}
export interface StatRow {
  session_id: string;
  session_title: string;
  group_id: string;
  group_name: string;
  starts_at: string;
  student_id: string;
  student_name: string;
  status: AttendanceStatus;
}
export interface Summary {
  id: string;
  label: string;
  PRESENT: number;
  LATE: number;
  ABSENT: number;
  EXCUSED: number;
}
export interface Stats extends Page<StatRow> {
  totals: Record<string, number>;
  rate: number | null;
  by_student: Summary[];
  by_session: Summary[];
}
