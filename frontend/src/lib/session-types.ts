import type { AcademicYearBrief, Campus, ClassBrief, MeResponse, Program, SectionBrief, StudentProfile } from "./types";

/** The non-sensitive slice of the session the UI actually renders. */
export interface SessionUser {
  id: number;
  email: string;
  fullName: string;
  initials: string;
  role: "STUDENT" | "CLASS_REPRESENTATIVE" | "TEACHER" | "ADMIN";
  phone: string;
  capabilities: string[];
  profile: StudentProfile | null;
}

export type MeResponse_ = MeResponse;

export type Capability =
  /* Student surface */
  | "view_dashboard"
  | "view_timetable"
  | "view_subjects"
  | "view_papers"
  | "practice_papers"
  | "view_results"
  | "view_attendance"
  | "view_assignments"
  | "submit_assignments"
  | "view_resources"
  | "view_announcements"
  | "view_notifications"
  | "view_calendar"
  | "submit_requests"
  | "submit_feedback"
  | "edit_profile_contact"
  | "change_password"
  | "submit_timetable"
  | "report_timetable_change"
  /* Staff surface — issued to TEACHER and/or ADMIN, never to a student */
  | "view_students"
  | "review_timetable_submissions"
  | "publish_timetable"
  | "manage_papers"
  | "publish_papers"
  | "manage_results"
  | "publish_results"
  | "manage_attendance"
  | "manage_assignments"
  | "manage_resources"
  | "manage_announcements"
  | "manage_academic_events"
  | "assign_class_representatives"
  | "review_requests"
  | "review_feedback"
  | "manage_students"
  | "view_audit_log";

export type PortalProfile = Pick<
  StudentProfile,
  "student_code" | "campus" | "program" | "class_room" | "section" | "academic_year" | "class_display"
> & {
  campus: Campus | null;
  program: Program | null;
  class_room: ClassBrief | null;
  section: SectionBrief | null;
  academic_year: AcademicYearBrief | null;
};
