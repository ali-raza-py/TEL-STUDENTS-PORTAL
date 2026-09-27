/**
 * Shared API types.
 *
 * These mirror the DRF serializers. They are hand-written rather than
 * generated so the contract is reviewable, and every field the UI renders must
 * be declared here — the components never reach into untyped payloads.
 */

export type Role = "STUDENT" | "CLASS_REPRESENTATIVE" | "TEACHER" | "ADMIN";

export interface Campus {
  id: number;
  code: string;
  name: string;
}

export interface Program {
  id: number;
  code: string;
  name: string;
  level: string;
}

export interface AcademicYearBrief {
  id: number;
  code: string;
  label: string;
  is_current: boolean;
}

export interface SectionBrief {
  id: number;
  name: string;
  display_name?: string;
}

export interface ClassBrief {
  id: number;
  code: string;
  name: string;
  display_name: string;
  campus_id?: number;
  program_id?: number;
}

export interface ClassDetail extends ClassBrief {
  program_name: string;
  campus_name: string;
  academic_year_label: string;
  sections: SectionBrief[];
}

export interface StudentProfile {
  id: number;
  student_code: string;
  roll_number: string;
  campus: Campus | null;
  program: Program | null;
  class_room: ClassBrief | null;
  section: SectionBrief | null;
  academic_year: AcademicYearBrief | null;
  class_display: string;
  status: string;
  date_of_birth: string | null;
  gender: string;
  blood_group: string;
  guardian_name: string;
  guardian_relation: string;
  guardian_phone: string;
  home_address: string;
  admission_date: string | null;
  photo_url: string | null;
  last_synced_from_tel: string | null;
}

export interface CurrentUser {
  id: number;
  email: string;
  full_name: string;
  role: Role;
  phone: string;
  initials: string;
  capabilities: string[];
  student_profile: StudentProfile | null;
}

export interface MeResponse {
  user: CurrentUser;
  roles: { code: string; label: string }[];
  capabilities: string[];
}

/* -------------------------------------------------------------------------- */
/* Pagination                                                                 */
/* -------------------------------------------------------------------------- */

export interface Paginated<T> {
  count: number;
  num_pages: number;
  page: number;
  page_size: number;
  has_next: boolean;
  has_previous: boolean;
  next: string | null;
  previous: string | null;
  results: T[];
}

/* -------------------------------------------------------------------------- */
/* Dashboard                                                                  */
/* -------------------------------------------------------------------------- */

export interface DashboardClassEntry {
  id: number;
  day: number;
  day_label: string;
  subject: string;
  subject_code: string;
  subject_color: SubjectColor;
  teacher: string;
  room: string;
  campus: string;
  start: string;
  end: string;
  start_label: string;
  end_label: string;
  is_current: boolean;
  is_past: boolean;
  note: string;
  is_today?: boolean;
  date?: string;
  starts_in_minutes?: number;
}

export interface AttendanceCard {
  available: boolean;
  message: string;
  overall_percentage: number | null;
  target_percentage: number;
  meets_target: boolean;
  lowest_subject: SubjectAttendance | null;
  monthly_trend: { label: string; percentage: number; total_classes: number }[];
}

export interface SubjectPerformanceRow {
  subject_id: number;
  subject_code: string;
  subject_name: string;
  subject_color: SubjectColor;
  average_percentage: number;
  assessments: number;
  best_percentage: number;
  latest_percentage: number | null;
  latest_assessment: string | null;
  latest_date: string | null;
  trend: { label: string; date: string; percentage: number }[];
  weakest_item: string | null;
}

export interface WeakSubjectRow {
  subject_id: number;
  subject_code: string;
  subject_name: string;
  subject_color: SubjectColor;
  recent_average: number;
  overall_average: number;
  assessments: number;
  threshold: number;
  severity: "high" | "moderate" | "watch";
  reason: string;
  recent_scores: { label: string; date: string; percentage: number }[];
  recommendation: string;
}

export interface PaperSummary {
  id: number;
  public_id: string;
  title: string;
  exam_type: string;
  exam_type_label: string;
  status: string;
  status_label: string;
  subject: number;
  subject_code: string;
  subject_name: string;
  subject_color: SubjectColor;
  class_room: number;
  class_name: string;
  section: number | null;
  section_name: string;
  campus: number;
  campus_name: string;
  academic_year: number;
  academic_year_label: string;
  teacher_name: string;
  total_marks: number;
  duration_minutes: number;
  exam_date: string | null;
  published_at: string | null;
  question_count: number;
  attempt_count: number;
  best_attempt_percentage: number | null;
  latest_attempt_percentage: number | null;
  attempts_remaining: number | null;
  can_practice: boolean;
  has_answer_key: boolean;
  has_topic_metadata: boolean;
  has_paper_file: boolean;
  allow_retake: boolean;
  attempt_limit: number;
}

export interface PaperDetail extends PaperSummary {
  instructions: string;
  paper_file_url: string | null;
  answer_key_file_url: string | null;
  source: string;
  external_ref: string;
  attempts: {
    id: number;
    attempt_number: number;
    status: string;
    score: number;
    total_marks: number;
    percentage: number | null;
    submitted_at: string | null;
  }[];
}

export interface DashboardData {
  generated_at: string;
  identity: {
    greeting: string;
    first_name: string;
    full_name: string;
    student_code: string;
    campus: string;
    program: string;
    class_name: string;
    class_display: string;
    section: string;
    academic_year: string;
    profile_photo_url: string | null;
  };
  timetable: {
    published: boolean;
    version: number | null;
    published_at: string | null;
    message: string;
  };
  next_class: DashboardClassEntry | null;
  today_classes: DashboardClassEntry[];
  upcoming_test: {
    available: boolean;
    message: string;
    paper_id?: number;
    title?: string;
    subject?: string;
    subject_code?: string;
    subject_color?: SubjectColor;
    date?: string;
    total_marks?: number;
    duration_minutes?: number;
    days_away?: number;
    relative?: string;
  };
  due_assignments: {
    available: boolean;
    message: string;
    count: number;
    next?: {
      id: number;
      title: string;
      subject: string;
      subject_color: SubjectColor;
      due_on: string;
      days_remaining: number;
    };
  };
  attendance: AttendanceCard;
  performance: {
    available: boolean;
    message: string;
    overall_average: number | null;
    subjects: SubjectPerformanceRow[];
  };
  recent_result: {
    assessment_name: string;
    subject: string;
    subject_code: string;
    subject_color: SubjectColor;
    obtained_marks: number;
    total_marks: number;
    percentage: number;
    grade: string;
    date: string;
  } | null;
  practice: {
    available_papers: number;
    papers: PaperSummary[];
    attempts: number;
    best_percentage: number | null;
  };
  weak_subjects: WeakSubjectRow[];
  announcements: {
    id: number;
    title: string;
    body: string;
    audience_label: string;
    scope: string;
    author: string;
    published_at: string;
    is_pinned: boolean;
  }[];
  events: {
    id: number;
    title: string;
    event_type: string;
    event_type_label: string;
    starts_at: string;
    is_all_day: boolean;
    subject_color: SubjectColor;
  }[];
  notifications: { unread: number };
  thresholds: { weak_subject_score: number; attendance_target: number };
}

export interface DashboardUnavailable {
  available: false;
  reason: string;
  message: string;
}

/* -------------------------------------------------------------------------- */
/* Timetable                                                                  */
/* -------------------------------------------------------------------------- */

export type SubjectColor =
  | "sage"
  | "mint"
  | "sky"
  | "sand"
  | "clay"
  | "lilac";

export interface TimetableEntry {
  id: number;
  day_of_week: number;
  day_label: string;
  start_time: string;
  end_time: string;
  start_label: string;
  end_label: string;
  subject: number;
  subject_code: string;
  subject_name: string;
  subject_color: SubjectColor;
  teacher_name: string;
  room: string;
  campus: number | null;
  note: string;
}

export interface TimetableVersion {
  id: number;
  public_id: string;
  class_room: number;
  class_name: string;
  section: number;
  section_name: string;
  campus_name: string;
  academic_year: number;
  version: number;
  version_label: string;
  status: string;
  status_label: string;
  title: string;
  effective_from: string | null;
  change_note: string;
  source: string;
  created_by_name: string;
  approved_by_name: string;
  approved_at: string | null;
  published_at: string | null;
  archived_at: string | null;
  entries: TimetableEntry[];
}

export interface TimetableResponse {
  timetable: TimetableVersion | null;
  class: ClassDetail | null;
  server_time?: string;
  meta?: { message?: string };
}

export interface TodayResponse {
  has_timetable: boolean;
  date: string;
  weekday: number;
  timetable_version?: number;
  timetable_published_at?: string | null;
  today: DashboardClassEntry[];
  next_class: (DashboardClassEntry & {
    day_label: string;
    starts_in_minutes: number;
  }) | null;
  message?: string;
}

export type SubmissionStatus =
  | "DRAFT"
  | "SUBMITTED"
  | "UNDER_REVIEW"
  | "APPROVED"
  | "PUBLISHED"
  | "REJECTED"
  | "CHANGES_REQUESTED"
  | "ARCHIVED";

export interface TimetableSubmission {
  id: number;
  public_id: string;
  class_room: number;
  class_name: string;
  section: number;
  section_name: string;
  submitted_by_name: string;
  status: SubmissionStatus;
  status_label: string;
  summary: string;
  change_note: string;
  review_note: string;
  reviewed_by_name: string;
  reviewed_at: string | null;
  entries_payload: {
    day: number;
    start: string;
    end: string;
    subject_code: string;
    room?: string;
    note?: string;
  }[];
  image_url: string | null;
  pdf_url: string | null;
  entry_count: number;
  created_at: string;
}

export interface ClassToolkitAssignment {
  class_id: number;
  section_id: number;
  class_name: string;
  section_name: string;
  assigned_at: string;
  ends_on: string | null;
  subjects: {
    subject__id: number;
    subject__code: string;
    subject__name: string;
    teacher__full_name: string;
  }[];
}

/* -------------------------------------------------------------------------- */
/* Subjects / papers / practice                                                */
/* -------------------------------------------------------------------------- */

export interface SubjectOffering {
  subject_id: number;
  subject_code: string;
  subject_name: string;
  subject_kind: string;
  teacher_id: number | null;
  teacher_name: string;
  paper_count: number;
  resource_count: number;
}

export interface PracticeQuestion {
  id: number;
  order: number;
  question_type: "MCQ" | "TRUE_FALSE" | "SHORT" | "SUBJECTIVE";
  text: string;
  options: string[];
  marks: number;
  chapter: string;
}

export interface SavedAnswer {
  question_id: number;
  selected_option: number | null;
  text_answer: string;
}

export interface PracticeSession {
  attempt_id: number;
  paper: PaperDetail;
  questions: PracticeQuestion[];
  saved_answers: SavedAnswer[];
  attempt_number: number;
  started_at: string;
  time_remaining_seconds: number | null;
  resume: boolean;
}

export interface PracticeResultPayload {
  attempt_id: number;
  paper_id: number;
  paper_title: string;
  subject: string;
  attempt_number: number;
  score: number;
  total_marks: number;
  percentage: number | null;
  grade: string;
  correct: number;
  incorrect: number;
  unanswered: number;
  pending_review: number;
  time_taken_seconds: number;
  has_answer_key: boolean;
  notes: string;
}

export interface PracticeReviewItem {
  question_id: number;
  order: number;
  question_type: string;
  text: string;
  options: string[];
  marks: number;
  selected_option: number | null;
  text_answer: string;
  is_correct: boolean | null;
  marks_awarded: number;
  is_auto_graded: boolean;
  correct_option: number | null;
  explanation: string;
  pending_review: boolean;
}

export interface PracticeHistoryRow {
  attempt_id: number;
  paper_id: number;
  paper_title: string;
  subject_code: string;
  subject_name: string;
  subject_color: SubjectColor;
  exam_type_label: string;
  attempts: {
    id: number;
    attempt_number: number;
    score: number;
    total_marks: number;
    percentage: number | null;
    status: string;
    submitted_at: string | null;
    time_taken_seconds: number;
  }[];
  attempt_number: number;
  score: number;
  total_marks: number;
  percentage: number | null;
  status: string;
  submitted_at: string | null;
  time_taken_seconds: number;
  improvement: number | null;
}

/* -------------------------------------------------------------------------- */
/* Results                                                                    */
/* -------------------------------------------------------------------------- */

export interface ResultItem {
  id: number;
  question_label: string;
  chapter: string;
  topic: string;
  marks_awarded: number;
  marks_total: number;
}

export interface ResultRow {
  id: number;
  assessment_name: string;
  assessment_type: string;
  assessment_type_label: string;
  assessment_date: string;
  subject: number;
  subject_code: string;
  subject_name: string;
  subject_color: SubjectColor;
  paper: number | null;
  paper_title: string;
  obtained_marks: number;
  total_marks: number;
  percentage: number;
  grade: string;
  position_in_class: number | null;
  remarks: string;
  status: string;
  status_label: string;
  published_at: string | null;
  items: ResultItem[];
  has_topic_breakdown: boolean;
}

export interface TopicAnalysisResponse {
  available: boolean;
  reason: string;
  topics: {
    subject_id: number;
    subject_code: string;
    subject_name: string;
    chapter: string;
    topic: string;
    obtained: number;
    total: number;
    percentage: number;
    status: "strong" | "steady" | "needs_attention";
  }[];
}

/* -------------------------------------------------------------------------- */
/* Attendance                                                                 */
/* -------------------------------------------------------------------------- */

export interface SubjectAttendance {
  subject_id: number;
  subject_code: string;
  subject_name: string;
  subject_color: SubjectColor;
  percentage: number;
  present: number;
  absent: number;
  late: number;
  excused: number;
  on_duty: number;
  total_classes: number;
}

export interface AttendanceRecordRow {
  id: number;
  date: string;
  subject_id: number;
  subject_code: string;
  subject_name: string;
  subject_color: SubjectColor;
  status: string;
  status_label: string;
  period_label: string;
  note: string;
}

export interface AttendanceSummary {
  available: boolean;
  message: string;
  overall_percentage: number | null;
  total_classes?: number;
  attended_classes?: number;
  counts?: Record<string, number>;
  subjects: SubjectAttendance[];
  recent: AttendanceRecordRow[];
  monthly_trend: { label: string; percentage: number; total_classes: number }[];
  lowest_subject: SubjectAttendance | null;
  target_percentage: number;
  meets_target: boolean;
}

/* -------------------------------------------------------------------------- */
/* Engagement                                                                 */
/* -------------------------------------------------------------------------- */

export interface AssignmentRow {
  id: number;
  public_id: string;
  title: string;
  description: string;
  subject: number;
  subject_code: string;
  subject_name: string;
  subject_color: SubjectColor;
  teacher_name: string;
  class_name: string;
  assigned_on: string;
  due_on: string;
  max_marks: number;
  attachment_url: string | null;
  attachment_name: string;
  status: "NOT_STARTED" | "IN_PROGRESS" | "SUBMITTED" | "LATE" | "REVIEWED";
  days_remaining: number;
  is_overdue: boolean;
  submission: {
    id: number;
    status: string;
    file_url: string | null;
    notes: string;
    submitted_at: string;
    reviewed_at: string | null;
    feedback: string;
    marks_awarded: number | null;
  } | null;
}

export interface ResourceRow {
  id: number;
  public_id: string;
  title: string;
  description: string;
  category: string;
  category_label: string;
  subject: number | null;
  subject_code: string;
  subject_name: string;
  subject_color: SubjectColor;
  class_name: string;
  chapter: string;
  academic_year_label: string;
  file_url: string | null;
  file_name: string;
  file_size: number | null;
  content_type: string | null;
  external_url: string;
  is_published: boolean;
  published_at: string | null;
}

export interface AnnouncementRow {
  id: number;
  public_id: string;
  title: string;
  body: string;
  audience: string;
  audience_label: string;
  campus_name: string;
  program_name: string;
  class_name: string;
  section_name: string;
  academic_year_label: string;
  author_name: string;
  attachment_url: string | null;
  attachment_name: string;
  is_pinned: boolean;
  published_at: string;
  expires_at: string | null;
  is_expired: boolean;
}

export interface AcademicEventRow {
  id: number;
  public_id: string;
  title: string;
  description: string;
  event_type: string;
  event_type_label: string;
  starts_at: string;
  ends_at: string | null;
  is_all_day: boolean;
  subject_name: string;
  subject_color: SubjectColor;
  campus_name: string;
}

export interface CalendarResponse {
  range: { from: string; to: string };
  events: AcademicEventRow[];
}

export interface NotificationRow {
  id: number;
  category: string;
  state: string;
  is_read: boolean;
  title: string;
  body: string;
  action_url: string;
  action_label: string;
  created_at: string;
  read_at: string | null;
}

export interface RequestRow {
  id: number;
  ticket_id: string;
  request_type: string;
  request_type_label: string;
  subject_line: string;
  description: string;
  related_date: string | null;
  attachment_url: string | null;
  attachment_name: string;
  status: "PENDING" | "IN_REVIEW" | "RESOLVED" | "REJECTED" | "CLOSED";
  status_label: string;
  admin_response: string;
  responded_by_name: string;
  responded_at: string | null;
  created_at: string;
  updated_at: string;
  student_name: string;
  student_code: string;
}

export interface FeedbackRow {
  id: number;
  category: string;
  category_label: string;
  rating: number | null;
  message: string;
  status: string;
  created_at: string;
}

/* -------------------------------------------------------------------------- */
/* Reference data                                                             */
/* -------------------------------------------------------------------------- */

export interface LookupData {
  campuses: Campus[];
  programs: Program[];
  classes: (ClassBrief & {
    academic_year_id: number;
    section_count: number;
  })[];
  sections: (SectionBrief & { class_id: number; student_count: number })[];
  subjects: { id: number; code: string; name: string; program_id: number }[];
  academic_years: (AcademicYearBrief & { class_count: number })[];
}

export interface ChoiceOption {
  value: string;
  label: string;
}

export interface IntegrationStatus {
  adapter: string;
  mode: string;
  healthy: boolean;
  message: string;
  entities: string[];
}

export interface ApiErrorBody {
  error: {
    code: string;
    message: string;
    details: Record<string, unknown>;
    trace_id: string | null;
  };
}
