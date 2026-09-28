"use client";

import Link from "next/link";
import { ChevronRight, Target, BookOpen, Award } from "lucide-react";

import { PageHeader, PageStack, SectionHeading } from "@/components/ui/page-header";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge, ToneBadge } from "@/components/ui/badge";
import { BarRow } from "@/components/ui/progress";
import { subjectToken, formatPercent, formatDate, statusTone, cn, type Tone } from "@/lib/utils";
import type { DashboardData } from "@/lib/types";
import {
  EducationalCard,
  StatCard,
  SubjectPill,
  ProgressRingAnimated,
  PageTransitionWrapper,
} from "@/components/education/education-components";

/**
 * Student dashboard.
 *
 * Purely presentational — the payload is fetched once by the page and routed
 * here by role. Teachers and administrators get their own role shaped
 * dashboards instead.
 */
export function StudentDashboard({ data }: { data: DashboardData }) {
  const d = data;
  const token = (color: string | null | undefined) => subjectToken(color ?? "sage");

  return (
    <>
      <PageTransitionWrapper>
        <PageStack className="relative z-10">
          <PageHeader
            title={`Good ${timeGreeting()}, ${d.identity.first_name}`}
            description={d.identity.class_display}
            actions={
              <Button asChild variant="soft" size="sm" icon={<ChevronRight className="h-3.5 w-3.5" />}>
                <Link href="/profile">View full profile</Link>
              </Button>
            }
          />

          {d.next_class ? <NextClassCard entry={d.next_class} /> : null}

          {d.today_classes.length > 0 && (
            <div className="space-y-3 animate-stagger-1">
              <SectionHeading title="Today's schedule" />
              <div className="grid gap-2.5 sm:grid-cols-2 xl:grid-cols-3">
                {d.today_classes.map((entry) => (
                  <TodayClassCard key={`${entry.subject}-${entry.start}`} entry={entry} />
                ))}
              </div>
            </div>
          )}

          {d.attendance.available && (
            <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4 animate-stagger-2">
              <EducationalCard variant="elevated">
                <StatCard
                  label="Attendance"
                  value={formatPercent(d.attendance.overall_percentage)}
                  hint={
                    d.attendance.meets_target
                      ? `Meets target of ${formatPercent(d.attendance.target_percentage)}`
                      : `Below target of ${formatPercent(d.attendance.target_percentage)}`
                  }
                  trend={`${d.attendance.meets_target ? "+" : "-"}${Math.abs((d.attendance.overall_percentage ?? 0) - d.attendance.target_percentage).toFixed(1)}%`}
                  trendUp={d.attendance.meets_target}
                  icon={<ProgressRingAnimated value={d.attendance.overall_percentage ?? 0} size={56} color="success" />}
                />
              </EducationalCard>
              {d.recent_result && (
                <EducationalCard variant="elevated">
                  <StatCard
                    label="Latest result"
                    value={`${d.recent_result.obtained_marks}/${d.recent_result.total_marks}`}
                    hint={formatPercent(d.recent_result.percentage)}
                    trend={`${d.recent_result.percentage >= 70 ? "+" : "-"}${Math.abs(d.recent_result.percentage - 70).toFixed(1)}%`}
                    trendUp={d.recent_result.percentage >= 70}
                    icon={<BookOpen className="h-5 w-5" />}
                    iconColor="warning"
                  />
                </EducationalCard>
              )}
              <EducationalCard variant="elevated" icon={<BookOpen className="h-5 w-5" />} iconColor="brand">
                <StatCard
                  label="Practice papers"
                  value={d.practice.papers.length}
                  hint={
                    d.practice.best_percentage !== null
                      ? `Best: ${formatPercent(d.practice.best_percentage)}`
                      : "No attempts yet"
                  }
                  trend={d.practice.attempts > 0 ? `+${d.practice.attempts} attempts` : "Start practicing"}
                  trendUp={d.practice.attempts > 0}
                />
              </EducationalCard>
              <EducationalCard variant="elevated" icon={<Target className="h-5 w-5" />} iconColor={d.due_assignments.count > 0 ? "danger" : "success"}>
                <StatCard
                  label="Due assignments"
                  value={d.due_assignments.count}
                  hint={
                    d.due_assignments.next
                      ? `${d.due_assignments.next.subject} — ${formatDate(d.due_assignments.next.due_on)}`
                      : d.due_assignments.message
                  }
                  trend={d.due_assignments.count > 0 ? `${d.due_assignments.count} pending` : "All caught up"}
                  trendUp={d.due_assignments.count === 0}
                />
              </EducationalCard>
            </div>
          )}

          {d.performance.available && d.performance.subjects.length > 0 && (
            <div className="space-y-3 animate-stagger-3">
              <SectionHeading
                title="Performance"
                actions={
                  <Link href="/results/analytics" className="text-small font-medium text-brand underline underline-offset-2">
                    View analytics
                  </Link>
                }
              />
              <div className="space-y-2">
                {d.performance.subjects.map((subject) => (
                  <EducationalCard key={subject.subject_id} variant="default" className="p-4">
                    <SubjectPill color={subject.subject_color as never} size="sm">
                      {subject.subject_name}
                    </SubjectPill>
                    <BarRow
                      label=""
                      value={formatPercent(subject.average_percentage)}
                      caption={`Best: ${formatPercent(subject.best_percentage)} · Last: ${formatPercent(subject.latest_percentage)}`}
                      barClassName={token(subject.subject_color).bar}
                    />
                  </EducationalCard>
                ))}
              </div>
            </div>
          )}

          {d.weak_subjects.length > 0 && (
            <div className="space-y-3 animate-stagger-4">
              <SectionHeading title="Needs attention" />
              <div className="space-y-2">
                {d.weak_subjects.map((ws) => (
                  <EducationalCard key={ws.subject_id} variant="default" className="p-4">
                    <div className="flex items-start gap-3">
                      <SubjectPill color={ws.subject_color as never} size="sm">
                        {ws.subject_name}
                      </SubjectPill>
                      <div className="min-w-0 flex-1">
                        <p className="font-medium text-ink">{ws.subject_name}</p>
                        <p className="text-small text-ink-muted">{ws.reason}</p>
                        <p className="mt-1 text-caption text-ink-soft">{ws.recommendation}</p>
                      </div>
                      <ToneBadge tone={weakSeverityTone(ws.severity)}>{ws.severity}</ToneBadge>
                    </div>
                  </EducationalCard>
                ))}
              </div>
            </div>
          )}

          <div className="grid gap-4 sm:grid-cols-2 animate-stagger-5">
            <Link href="/practice" className="group">
              <EducationalCard variant="elevated">
                <StatCard label="Practice" value={d.practice.attempts} hint="attempts made" icon={<BookOpen className="h-5 w-5" />} iconColor="brand" />
              </EducationalCard>
            </Link>
            <Link href="/announcements" className="group">
              <EducationalCard variant="elevated">
                <StatCard label="Announcements" value={d.announcements.length} hint="unread updates" icon={<Award className="h-5 w-5" />} iconColor="info" />
              </EducationalCard>
            </Link>
          </div>

          {d.upcoming_test.available && d.upcoming_test.paper_id && (
            <EducationalCard variant="elevated" icon={<Target className="h-5 w-5" />} iconColor="warning" className="animate-stagger-6">
              <StatCard
                label="Upcoming test"
                value={d.upcoming_test.title ?? "Unknown"}
                hint={`${formatDate(d.upcoming_test.date)} · ${d.upcoming_test.total_marks} marks`}
                trend="Coming soon"
                trendUp
              />
            </EducationalCard>
          )}
        </PageStack>
      </PageTransitionWrapper>
    </>
  );
}

function timeGreeting(): "morning" | "afternoon" | "evening" {
  const hour = new Date().getHours();
  if (hour < 12) return "morning";
  if (hour < 17) return "afternoon";
  return "evening";
}

function weakSeverityTone(severity: string): Tone {
  switch (severity) {
    case "high":
      return "danger";
    case "moderate":
      return "warning";
    case "watch":
      return "info";
    default:
      return "neutral";
  }
}

function NextClassCard({ entry }: { entry: DashboardData["next_class"] }) {
  if (!entry) return null;
  return (
    <Card className="p-5">
      <div className="flex items-center gap-4">
        <div className="flex-1">
          <p className="text-label font-bold uppercase text-ink-faint">Next class</p>
          <p className="mt-1 font-display text-h3 text-ink">{entry.subject}</p>
          <p className="text-small text-ink-muted">
            {entry.teacher} · {entry.room} · {entry.start_label} – {entry.end_label}
          </p>
        </div>
        <ToneBadge tone={statusTone(entry.is_current ? "current" : "scheduled")}>
          {entry.is_current ? "In progress" : "Upcoming"}
        </ToneBadge>
      </div>
    </Card>
  );
}

function TodayClassCard({ entry }: { entry: DashboardData["today_classes"][number] }) {
  return (
    <Card className="p-4">
      <div className="flex items-center gap-3">
        <span className={cn("h-3 w-3 shrink-0 rounded-full", subjectToken(entry.subject_color).dot)} />
        <div className="min-w-0 flex-1">
          <p className="font-medium text-ink">{entry.subject}</p>
          <p className="text-caption text-ink-muted">
            {entry.teacher} · {entry.start_label} – {entry.end_label}
          </p>
        </div>
        {entry.is_current ? <Badge tone="solid" size="sm">Now</Badge> : null}
      </div>
    </Card>
  );
}
