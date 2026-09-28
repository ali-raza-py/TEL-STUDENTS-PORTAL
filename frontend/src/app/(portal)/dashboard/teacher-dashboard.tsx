"use client";

import Link from "next/link";
import {
  Users,
  BookOpen,
  Inbox,
  CalendarClock,
  TriangleAlert,
  ChevronRight,
} from "lucide-react";

import { PageHeader, PageStack, SectionHeading } from "@/components/ui/page-header";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge, ToneBadge } from "@/components/ui/badge";
import { BarRow } from "@/components/ui/progress";
import { EmptyState } from "@/components/ui/states";
import { formatDateTime, formatPercent, statusTone, subjectToken, cn } from "@/lib/utils";
import type { TeacherDashboard, StaffPeriod, StaffRequestRow } from "@/lib/types";
import {
  EducationalCard,
  StatCard,
  SubjectPill,
  PageTransitionWrapper,
} from "@/components/education/education-components";

/**
 * Teacher dashboard.
 *
 * Answers two questions a teacher actually opens the portal with: what am I
 * teaching today, and what is waiting for me to review. Every figure is scoped
 * server side to the classes this teacher is assigned to.
 */
export function TeacherDashboardView({ data }: { data: TeacherDashboard }) {
  const { identity, stats, queues, teaching, at_risk_students } = data;

  if (data.unplaced_hint) {
    return (
      <>
        <PageStack className="relative z-10">
          <PageHeader
            title={`${identity.greeting}, ${identity.first_name}`}
            description={identity.designation || "Teacher"}
          />
          <EmptyState title="No classes assigned yet" description={data.unplaced_hint} icon={<Users className="h-5 w-5" />} />
        </PageStack>
      </>
    );
  }

  return (
    <>
      <PageTransitionWrapper>
        <PageStack className="relative z-10">
          <PageHeader
            eyebrow="Teacher"
            title={`${identity.greeting}, ${identity.first_name}`}
            description={[identity.designation, identity.campus].filter(Boolean).join(" · ") || "Teaching overview"}
            actions={
              <Button asChild variant="soft" size="sm" icon={<ChevronRight className="h-3.5 w-3.5" />}>
                <Link href="/profile">View profile</Link>
              </Button>
            }
          />

          {data.next_class ? <NextPeriodCard period={data.next_class} /> : null}

          {/* Workload */}
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4 animate-stagger-1">
            <EducationalCard variant="elevated">
              <StatCard
                label="My students"
                value={stats.students}
                hint={`across ${stats.classes} class${stats.classes === 1 ? "" : "es"}`}
                icon={<Users className="h-5 w-5" />}
                iconColor="brand"
              />
            </EducationalCard>
            <EducationalCard variant="elevated">
              <StatCard
                label="Subjects"
                value={stats.subjects}
                hint={`${stats.papers} paper${stats.papers === 1 ? "" : "s"} authored`}
                icon={<BookOpen className="h-5 w-5" />}
                iconColor="mint"
              />
            </EducationalCard>
            <EducationalCard variant="elevated">
              <StatCard
                label="To review"
                value={stats.unreviewed_submissions}
                hint="assignment submissions"
                trend={stats.unreviewed_submissions > 0 ? "Waiting on you" : "All reviewed"}
                trendUp={stats.unreviewed_submissions === 0}
                icon={<Inbox className="h-5 w-5" />}
                iconColor={stats.unreviewed_submissions > 0 ? "warning" : "success"}
              />
            </EducationalCard>
            <EducationalCard variant="elevated">
              <StatCard
                label="Open items"
                value={stats.timetable_queue + stats.open_requests}
                hint={`${stats.timetable_queue} timetable · ${stats.open_requests} requests`}
                icon={<CalendarClock className="h-5 w-5" />}
                iconColor="info"
              />
            </EducationalCard>
          </div>

          {/* Today's teaching */}
          {data.today_classes.length > 0 && (
            <div className="space-y-3 animate-stagger-2">
              <SectionHeading title="Today's teaching" />
              <div className="grid gap-2.5 sm:grid-cols-2 xl:grid-cols-3">
                {data.today_classes.map((period) => (
                  <PeriodCard key={period.id} period={period} />
                ))}
              </div>
            </div>
          )}

          {/* My classes */}
          {teaching.length > 0 && (
            <div className="space-y-3 animate-stagger-3">
              <SectionHeading title="My classes" />
              <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
                {teaching.map((row) => (
                  <EducationalCard key={`${row.class_id}-${row.section_id ?? "all"}`} variant="default" className="p-4">
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0">
                        <p className="truncate font-medium text-ink">{row.class_name}</p>
                        <p className="text-caption text-ink-muted">
                          {row.section_name}
                          {row.campus ? ` · ${row.campus}` : ""}
                        </p>
                      </div>
                      <Badge tone="neutral" size="sm">
                        {row.student_count} students
                      </Badge>
                    </div>
                    <div className="mt-3 flex flex-wrap gap-1.5">
                      {row.subjects.map((subject) => (
                        <SubjectPill key={subject.id} color={subject.color as never} size="sm">
                          {subject.name}
                        </SubjectPill>
                      ))}
                    </div>
                  </EducationalCard>
                ))}
              </div>
            </div>
          )}

          {/* Submissions needing review */}
          <QueueSection
            title="Submissions to review"
            count={queues.unreviewed_submissions.length}
            emptyText="Every submission in your classes has been reviewed."
            href="/assignments"
            hrefLabel="Open assignments"
          >
            {queues.unreviewed_submissions.map((row) => (
              <li key={row.id}>
                <EducationalCard variant="default" className="p-4">
                  <div className="flex items-start gap-3">
                    <span className={cn("mt-1.5 h-2.5 w-2.5 shrink-0 rounded-full", subjectToken(row.subject_color).dot)} />
                    <div className="min-w-0 flex-1">
                      <p className="truncate font-medium text-ink">{row.assignment_title}</p>
                      <p className="text-caption text-ink-muted">
                        {row.student_name}
                        {row.student_code ? ` (${row.student_code})` : ""} · {row.subject}
                      </p>
                    </div>
                    <div className="flex shrink-0 flex-col items-end gap-1">
                      <ToneBadge tone={statusTone(row.status)}>{row.status}</ToneBadge>
                      <span className="text-caption text-ink-faint">{formatDateTime(row.submitted_at)}</span>
                    </div>
                  </div>
                </EducationalCard>
              </li>
            ))}
          </QueueSection>

          {/* Timetable submissions */}
          <QueueSection
            title="Timetable submissions"
            count={queues.timetable_submissions.length}
            emptyText="No timetable changes are waiting for review."
            href="/timetable"
            hrefLabel="Open timetable"
          >
            {queues.timetable_submissions.map((row) => (
              <li key={row.id}>
                <EducationalCard variant="default" className="p-4">
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <p className="truncate font-medium text-ink">
                        {row.class_name} — {row.section_name}
                      </p>
                      <p className="truncate text-caption text-ink-muted">
                        {row.submitted_by ? `Submitted by ${row.submitted_by}` : "Submitted by a class representative"}
                        {row.summary ? ` · ${row.summary}` : ""}
                      </p>
                    </div>
                    <ToneBadge tone={statusTone(row.status)}>{row.status.replace(/_/g, " ")}</ToneBadge>
                  </div>
                </EducationalCard>
              </li>
            ))}
          </QueueSection>

          {/* Student requests */}
          <QueueSection
            title="Student requests"
            count={queues.open_requests.length}
            emptyText="No open requests from your students."
            href="/requests"
            hrefLabel="Open requests"
          >
            {queues.open_requests.map((row) => (
              <RequestRow key={row.id} row={row} />
            ))}
          </QueueSection>

          {/* Attendance risk */}
          {at_risk_students.length > 0 && (
            <div className="space-y-3 animate-stagger-4">
              <SectionHeading
                title="Attendance below target"
                description="Trailing 90 days across your classes"
              />
              <EducationalCard variant="default" className="divide-y divide-line-soft">
                {at_risk_students.map((student) => (
                  <div key={student.id} className="p-4 first:pt-4 last:pb-4">
                    <BarRow
                      label={
                        <span>
                          {student.name}
                          <span className="ml-2 font-mono text-caption text-ink-faint">{student.student_code}</span>
                        </span>
                      }
                      value={formatPercent(student.percentage)}
                      caption={`${student.class_name}${student.section_name ? ` — ${student.section_name}` : ""} · ${student.sessions} sessions`}
                      barClassName={subjectToken("clay").bar}
                      trailing={<TriangleAlert className="h-4 w-4 text-danger" aria-hidden />}
                    />
                  </div>
                ))}
              </EducationalCard>
            </div>
          )}
        </PageStack>
      </PageTransitionWrapper>
    </>
  );
}

/* -------------------------------------------------------------------------- */
/* Pieces                                                                      */
/* -------------------------------------------------------------------------- */

function QueueSection({
  title,
  count,
  emptyText,
  href,
  hrefLabel,
  children,
}: {
  title: string;
  count: number;
  emptyText: string;
  href: string;
  hrefLabel: string;
  children: React.ReactNode;
}) {
  return (
    <div className="space-y-3">
      <SectionHeading
        title={title}
        description={count > 0 ? `${count} item${count === 1 ? "" : "s"} waiting` : undefined}
        actions={
          <Link href={href} className="text-small font-medium text-brand underline underline-offset-2">
            {hrefLabel}
          </Link>
        }
      />
      {count === 0 ? (
        <EducationalCard variant="default" className="p-5">
          <p className="text-small text-ink-muted">{emptyText}</p>
        </EducationalCard>
      ) : (
        <ul className="space-y-2">{children}</ul>
      )}
    </div>
  );
}

function RequestRow({ row }: { row: StaffRequestRow }) {
  return (
    <li>
      <EducationalCard variant="default" className="p-4">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <p className="truncate font-medium text-ink">{row.subject_line}</p>
            <p className="truncate text-caption text-ink-muted">
              <span className="font-mono">{row.ticket_id}</span> · {row.request_type_label}
              {row.class_name ? ` · ${row.class_name}` : ""} · {row.student_name}
            </p>
          </div>
          <ToneBadge tone={statusTone(row.status)}>{row.status.replace(/_/g, " ")}</ToneBadge>
        </div>
      </EducationalCard>
    </li>
  );
}

function NextPeriodCard({ period }: { period: StaffPeriod }) {
  return (
    <Card className="p-5">
      <div className="flex items-center gap-4">
        <div className="flex-1">
          <p className="text-label font-bold uppercase text-ink-faint">Next class</p>
          <p className="mt-1 font-display text-h3 text-ink">{period.subject}</p>
          <p className="text-small text-ink-muted">
            {period.class_name}
            {period.section_name ? ` — ${period.section_name}` : ""} · {period.room} · {period.start_label} – {period.end_label}
          </p>
        </div>
        <ToneBadge tone={period.is_current ? "success" : "neutral"}>
          {period.is_current ? "In progress" : (period.day_label ?? "Upcoming")}
        </ToneBadge>
      </div>
    </Card>
  );
}

function PeriodCard({ period }: { period: StaffPeriod }) {
  return (
    <Card className={cn("p-4", period.is_current && "border-brand/40 bg-brand-tint/30")}>
      <div className="flex items-center gap-3">
        <span className={cn("h-3 w-3 shrink-0 rounded-full", subjectToken(period.subject_color).dot)} />
        <div className="min-w-0 flex-1">
          <p className="truncate font-medium text-ink">{period.subject}</p>
          <p className="truncate text-caption text-ink-muted">
            {period.class_name}
            {period.section_name ? ` — ${period.section_name}` : ""}
          </p>
          <p className="text-caption text-ink-faint">
            {period.start_label} – {period.end_label}
            {period.room ? ` · ${period.room}` : ""}
          </p>
        </div>
        {period.is_current ? <Badge tone="solid" size="sm">Now</Badge> : null}
      </div>
    </Card>
  );
}
