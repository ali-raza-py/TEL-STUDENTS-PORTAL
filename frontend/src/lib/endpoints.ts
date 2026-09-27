/**
 * Endpoint registry.
 *
 * Paths live in one file so a backend route change is a single edit rather than
 * a search across components.
 */

import type { RequestOptions } from "./api-client";
import { api } from "./api-client";
import type {
  AcademicEventRow,
  AcademicYearBrief,
  AnnouncementRow,
  AssignmentRow,
  AttendanceRecordRow,
  AttendanceSummary,
  CalendarResponse,
  ClassToolkitAssignment,
  DashboardData,
  DashboardUnavailable,
  FeedbackRow,
  LookupData,
  MeResponse,
  Paginated,
  PaperDetail,
  PaperSummary,
  PracticeHistoryRow,
  PracticeResultPayload,
  PracticeReviewItem,
  PracticeSession,
  RequestRow,
  ResourceRow,
  ResultRow,
  SubjectOffering,
  SubmissionStatus,
  TimetableResponse,
  TimetableSubmission,
  TimetableVersion,
  TodayResponse,
  TopicAnalysisResponse,
  WeakSubjectRow,
  SubjectPerformanceRow,
  IntegrationStatus,
} from "./types";

type Opt = Omit<RequestOptions, "method" | "body" | "query">;

export const endpoints = {
  auth: {
    login: (body: { email: string; password: string }) => api.post<MeResponse>("/api/auth/login/", body),
    logout: () => api.post<{ detail: string }>("/api/auth/logout/"),
    me: (o?: Opt) => api.get<MeResponse>("/api/auth/me/", o),
    profile: (o?: Opt) => api.get<MeResponse["user"]>("/api/auth/profile/", o),
    updateProfile: (body: Record<string, unknown>, o?: Opt) =>
      api.patch<MeResponse["user"]>("/api/auth/profile/", body, o),
    changePassword: (body: { current_password: string; new_password: string }, o?: Opt) =>
      api.post<{ detail: string }>("/api/auth/password/change/", body, o),
    forgotPassword: (body: { email: string }, o?: Opt) =>
      api.post<{ detail: string }>("/api/auth/password/forgot/", body, o),
  },

  dashboard: {
    get: (o?: Opt) =>
      api.get<DashboardData | DashboardUnavailable>("/api/dashboard/", o),
  },

  academics: {
    class: (o?: Opt) =>
      api.get<{ class: unknown; sections: unknown[]; campus: unknown; program: unknown; academic_year: AcademicYearBrief | null }>(
        "/api/class/",
        o,
      ),
    subjects: (o?: Opt) =>
      api.get<{ count: number; results: SubjectOffering[] }>("/api/subjects/", o),
    timetable: (o?: Opt) => api.get<TimetableResponse>("/api/timetable/", o),
    today: (o?: Opt) => api.get<TodayResponse>("/api/timetable/today/", o),
    versions: (o?: Opt) =>
      api.get<{ count: number; results: TimetableVersion[] }>("/api/timetable/versions/", o),
    submissions: (o?: Opt) =>
      api.get<{ count: number; results: TimetableSubmission[]; message?: string }>(
        "/api/timetable/submissions/",
        o,
      ),
    submitTimetable: (form: FormData) =>
      api.postForm<TimetableSubmission>("/api/timetable/submissions/", form),
    reviewSubmission: (id: number, body: { decision: string; note?: string }) =>
      api.post<TimetableSubmission>(`/api/timetable/submissions/${id}/review/`, body),
    publishSubmission: (id: number, body: { effective_from?: string; change_note?: string }) =>
      api.post<TimetableVersion>(`/api/timetable/submissions/${id}/publish/`, body),
    classToolkit: (o?: Opt) =>
      api.get<{ assignments: ClassToolkitAssignment[] }>("/api/class-toolkit/", o),
  },

  papers: {
    list: (query: RequestOptions["query"], o?: Opt) =>
      api.get<Paginated<PaperSummary>>("/api/student/papers/", { ...o, query }),
    detail: (id: number, o?: Opt) => api.get<PaperDetail>(`/api/papers/${id}/`, o),
    startPractice: (id: number) => api.post<PracticeSession>(`/api/papers/${id}/practice/`),
    save: (attemptId: number, answers: unknown[]) =>
      api.post<{ saved: number; saved_at: string }>(`/api/practice/${attemptId}/save/`, { answers }),
    submit: (attemptId: number, answers?: unknown[]) =>
      api.post<PracticeResultPayload>(`/api/practice/${attemptId}/submit/`, answers ? { answers } : {}),
    review: (attemptId: number, o?: Opt) =>
      api.get<{ review: PracticeReviewItem[]; message: string }>(
        `/api/practice/${attemptId}/review/`,
        o,
      ),
    history: (query: RequestOptions["query"], o?: Opt) =>
      api.get<Paginated<PracticeHistoryRow>>("/api/student/practice-history/", { ...o, query }),
    examTypes: (o?: Opt) =>
      api.get<{ value: string; label: string }[]>("/api/exam-types/", o),
  },

  results: {
    list: (query: RequestOptions["query"], o?: Opt) =>
      api.get<Paginated<ResultRow>>("/api/student/results/", { ...o, query }),
    analytics: (o?: Opt) =>
      api.get<{
        has_results: boolean;
        message: string;
        overall_average: number | null;
        subjects: SubjectPerformanceRow[];
        weak_subjects: WeakSubjectRow[];
        thresholds: Record<string, number>;
      }>("/api/student/analytics/", o),
    topics: (query: RequestOptions["query"], o?: Opt) =>
      api.get<TopicAnalysisResponse>("/api/student/analytics/topics/", { ...o, query }),
    progress: (o?: Opt) =>
      api.get<Record<string, unknown>>("/api/student/progress/", o),
  },

  attendance: {
    summary: (o?: Opt) => api.get<AttendanceSummary>("/api/student/attendance/", o),
    records: (query: RequestOptions["query"], o?: Opt) =>
      api.get<Paginated<AttendanceRecordRow>>("/api/student/attendance/records/", { ...o, query }),
  },

  engagement: {
    assignments: (query: RequestOptions["query"], o?: Opt) =>
      api.get<Paginated<AssignmentRow>>("/api/student/assignments/", { ...o, query }),
    submitAssignment: (id: number, form: FormData) =>
      api.postForm<AssignmentRow["submission"]>(`/api/assignments/${id}/submissions/`, form),
    resources: (query: RequestOptions["query"], o?: Opt) =>
      api.get<Paginated<ResourceRow>>("/api/student/resources/", { ...o, query }),
    resource: (id: number, o?: Opt) => api.get<ResourceRow>(`/api/resources/${id}/`, o),
    announcements: (query: RequestOptions["query"], o?: Opt) =>
      api.get<Paginated<AnnouncementRow>>("/api/student/announcements/", { ...o, query }),
    calendar: (query: RequestOptions["query"], o?: Opt) =>
      api.get<CalendarResponse>("/api/student/calendar/", { ...o, query }),
    requests: (query: RequestOptions["query"], o?: Opt) =>
      api.get<Paginated<RequestRow>>("/api/student/requests/", { ...o, query }),
    createRequest: (form: FormData) => api.postForm<RequestRow>("/api/student/requests/", form),
    feedback: (o?: Opt) =>
      api.get<{ count: number; results: FeedbackRow[] }>("/api/student/feedback/", o),
    createFeedback: (body: { category: string; rating?: number | null; message: string }) =>
      api.post<FeedbackRow>("/api/student/feedback/", body),
  },

  notifications: {
    list: (query: RequestOptions["query"], o?: Opt) =>
      api.get<{ results: import("./types").NotificationRow[]; unread_count: number }>(
        "/api/notifications/",
        { ...o, query },
      ),
    unreadCount: (o?: Opt) =>
      api.get<{ unread_count: number }>("/api/notifications/unread-count/", o),
    markRead: (body: { ids?: number[]; all?: boolean }) =>
      api.post<{ marked: number }>("/api/notifications/", body),
  },

  platform: {
    lookups: (query: RequestOptions["query"], o?: Opt) =>
      api.get<LookupData>("/api/lookups/", { ...o, query }),
    integrationStatus: (o?: Opt) => api.get<IntegrationStatus>("/api/integration/status/", o),
    health: (o?: Opt) =>
      api.get<{ status: string; database: string }>("/api/health/", o),
  },
};

export type SubmissionStatus_ = SubmissionStatus;
export type EventRow = AcademicEventRow;
