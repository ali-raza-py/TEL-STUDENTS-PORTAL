"use client";

import Link from "next/link";
import {
  Users,
  GraduationCap,
  School,
  UserRoundX,
  FileCheck2,
  FileStack,
  CalendarClock,
  LifeBuoy,
  ChevronRight,
  History,
  CalendarDays,
} from "lucide-react";

import { PageHeader, PageStack, SectionHeading } from "@/components/ui/page-header";
import { Button } from "@/components/ui/button";
import { ToneBadge } from "@/components/ui/badge";
import { BarRow } from "@/components/ui/progress";
import { formatDate, formatDateTime, formatMarks, formatPercent, statusTone, subjectToken, cn } from "@/lib/utils";
import type { AdminDashboard, StaffRequestRow } from "@/lib/types";
import {
  EducationalCard,
  StatCard,
  PageTransitionWrapper,
} from "@/components/education/education-components";

/**
 * Administrator dashboard.
 *
 * Institution wide: how many people are enrolled, and which review queue needs
 * an administrator next. Every queue is a count of work that is genuinely
 * outstanding, not a vanity metric.
 */
export function AdminDashboardView({ data }: { data: AdminDashboard }) {
  const { identity, stats, queues, enrolment } = data;
  const openItems =
    stats.papers_unverified +
    stats.results_unpublished +
    stats.timetable_queue +
    stats.open_requests;

  return (
    <>
      <PageTransitionWrapper>
        <PageStack className="relative z-10">
          <PageHeader
            eyebrow="Administration"
            title={`${identity.greeting}, ${identity.first_name}`}
            description={data.academic_year.is_current ? data.academic_year.label : "Institution overview"}
            actions={
              <Button asChild variant="soft" size="sm" icon={<ChevronRight className="h-3.5 w-3.5" />}>
                <Link href="/profile">View profile</Link>
              </Button>
            }
          />

          {/* Institution at a glance */}
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4 animate-stagger-1">
            <EducationalCard variant="elevated">
              <StatCard
                label="Students"
                value={stats.students}
                hint={`across ${stats.programs} programmes`}
                icon={<Users className="h-5 w-5" />}
                iconColor="brand"
              />
            </EducationalCard>
            <EducationalCard variant="elevated">
              <StatCard
                label="Teachers"
                value={stats.teachers}
                hint={`teaching ${stats.classes} classes`}
                icon={<GraduationCap className="h-5 w-5" />}
                iconColor="mint"
              />
            </EducationalCard>
            <EducationalCard variant="elevated">
              <StatCard
                label="Active classes"
                value={stats.classes}
                hint="in the current year"
                icon={<School className="h-5 w-5" />}
                iconColor="info"
              />
            </EducationalCard>
            <EducationalCard variant="elevated">
              <StatCard
                label="Unplaced students"
                value={stats.unplaced_students}
                hint="missing class placement"
                trend={stats.unplaced_students > 0 ? "Needs attention" : "All placed"}
                trendUp={stats.unplaced_students === 0}
                icon={<UserRoundX className="h-5 w-5" />}
                iconColor={stats.unplaced_students > 0 ? "danger" : "success"}
              />
            </EducationalCard>
          </div>

          {/* Work queues */}
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4 animate-stagger-2">
            <QueueStat
              label="Papers to verify"
              value={stats.papers_unverified}
              hint={`${stats.papers_draft} still in draft`}
              icon={<FileStack className="h-5 w-5" />}
              href="/papers"
            />
            <QueueStat
              label="Results to publish"
              value={stats.results_unpublished}
              hint="not yet visible to students"
              icon={<FileCheck2 className="h-5 w-5" />}
              href="/results"
            />
            <QueueStat
              label="Timetable queue"
              value={stats.timetable_queue}
              hint="submissions awaiting a decision"
              icon={<CalendarClock className="h-5 w-5" />}
              href="/timetable"
            />
            <QueueStat
              label="Open requests"
              value={stats.open_requests}
              hint={`${stats.new_feedback} new feedback items`}
              icon={<LifeBuoy className="h-5 w-5" />}
              href="/requests"
            />
          </div>

          {/* Enrolment breakdown */}
          {(enrolment.by_campus.length > 0 || enrolment.by_program.length > 0) && (
            <div className="grid gap-4 lg:grid-cols-2 animate-stagger-3">
              {enrolment.by_campus.length > 0 && (
                <EducationalCard variant="elevated" icon={<School className="h-5 w-5" />} iconColor="brand">
                  <h3 className="font-display text-h3 text-ink">Enrolment by campus</h3>
                  <div className="mt-4 space-y-3">
                    {enrolment.by_campus.map((row) => (
                      <BarRow
                        key={row.id}
                        label={row.name}
                        value={row.total}
                        barClassName={subjectToken("sky").bar}
                      />
                    ))}
                  </div>
                </EducationalCard>
              )}
              {enrolment.by_program.length > 0 && (
                <EducationalCard variant="elevated" icon={<GraduationCap className="h-5 w-5" />} iconColor="lilac">
                  <h3 className="font-display text-h3 text-ink">Enrolment by programme</h3>
                  <div className="mt-4 space-y-3">
                    {enrolment.by_program.map((row) => (
                      <BarRow
                        key={row.id}
                        label={row.name}
                        value={row.total}
                        barClassName={subjectToken("lilac").bar}
                      />
                    ))}
                  </div>
                </EducationalCard>
              )}
            </div>
          )}

          {/* Queues */}
          <AdminQueue
            title="Papers awaiting verification"
            rows={queues.papers_awaiting_verification}
            emptyText="No papers are waiting to be verified."
            href="/papers"
            hrefLabel="Manage papers"
            render={(row) => (
              <>
                <div className="min-w-0 flex-1">
                  <p className="truncate font-medium text-ink">{row.title}</p>
                  <p className="truncate text-caption text-ink-muted">
                    {row.subject}
                    {row.class_name ? ` · ${row.class_name}` : ""}
                    {row.teacher ? ` · ${row.teacher}` : ""}
                  </p>
                </div>
                <div className="flex shrink-0 flex-col items-end gap-1">
                  <span className="text-caption text-ink-muted">{formatMarks(row.total_marks)} marks</span>
                  <span className="text-caption text-ink-faint">{formatDate(row.created_at)}</span>
                </div>
              </>
            )}
          />

          <AdminQueue
            title="Results awaiting publication"
            rows={queues.results_awaiting_publication}
            emptyText="All results have been published to students."
            href="/results"
            hrefLabel="Manage results"
            render={(row) => (
              <>
                <div className="min-w-0 flex-1">
                  <p className="truncate font-medium text-ink">{row.assessment_name}</p>
                  <p className="truncate text-caption text-ink-muted">
                    {row.student_name} · {row.subject}
                  </p>
                </div>
                <div className="flex shrink-0 flex-col items-end gap-1">
                  <span className="text-caption font-medium text-ink">{formatPercent(row.percentage)}</span>
                  <ToneBadge tone={statusTone(row.status)}>{row.status}</ToneBadge>
                </div>
              </>
            )}
          />

          <AdminQueue
            title="Timetable submissions"
            rows={queues.timetable_submissions}
            emptyText="No timetable changes are waiting for a decision."
            href="/timetable"
            hrefLabel="Review timetable"
            render={(row) => (
              <>
                <div className="min-w-0 flex-1">
                  <p className="truncate font-medium text-ink">
                    {row.class_name} — {row.section_name}
                  </p>
                  <p className="truncate text-caption text-ink-muted">
                    {row.submitted_by ? `Submitted by ${row.submitted_by}` : "Submitted by a class representative"}
                    {row.summary ? ` · ${row.summary}` : ""}
                  </p>
                </div>
                <ToneBadge tone={statusTone(row.status)}>{row.status.replace(/_/g, " ")}</ToneBadge>
              </>
            )}
          />

          <AdminQueue
            title="Open student requests"
            rows={queues.open_requests}
            emptyText="No student requests are open."
            href="/requests"
            hrefLabel="Open requests"
            render={(row: StaffRequestRow) => (
              <>
                <div className="min-w-0 flex-1">
                  <p className="truncate font-medium text-ink">{row.subject_line}</p>
                  <p className="truncate text-caption text-ink-muted">
                    <span className="font-mono">{row.ticket_id}</span> · {row.request_type_label}
                    {row.class_name ? ` · ${row.class_name}` : ""} · {row.student_name}
                  </p>
                </div>
                <ToneBadge tone={statusTone(row.status)}>{row.status.replace(/_/g, " ")}</ToneBadge>
              </>
            )}
          />

          {/* Unplaced students */}
          {queues.unplaced_students.length > 0 && (
            <div className="space-y-3 animate-stagger-4">
              <SectionHeading
                title="Students missing a placement"
                description="These students cannot see any academic data until they are placed"
              />
              <ul className="space-y-2">
                {queues.unplaced_students.map((row) => (
                  <li key={row.id}>
                    <EducationalCard variant="default" className="p-4">
                      <div className="flex items-start justify-between gap-3">
                        <div className="min-w-0">
                          <p className="truncate font-medium text-ink">{row.name}</p>
                          <p className="font-mono text-caption text-ink-faint">{row.student_code}</p>
                        </div>
                        <ToneBadge tone="danger">Missing: {row.missing}</ToneBadge>
                      </div>
                    </EducationalCard>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Upcoming events */}
          {data.upcoming_events.length > 0 && (
            <div className="space-y-3 animate-stagger-4">
              <SectionHeading
                title="Coming up"
                actions={
                  <Link href="/calendar" className="text-small font-medium text-brand underline underline-offset-2">
                    Full calendar
                  </Link>
                }
              />
              <div className="grid gap-2.5 sm:grid-cols-2 xl:grid-cols-3">
                {data.upcoming_events.map((row) => (
                  <EducationalCard key={row.id} variant="default" className="p-4">
                    <div className="flex items-start gap-3">
                      <span className={cn("mt-1.5 h-2.5 w-2.5 shrink-0 rounded-full", subjectToken(row.subject_color).dot)} />
                      <div className="min-w-0 flex-1">
                        <p className="truncate font-medium text-ink">{row.title}</p>
                        <p className="truncate text-caption text-ink-muted">{row.event_type_label}</p>
                        <p className="text-caption text-ink-faint">
                          {row.is_all_day ? formatDate(row.starts_at) : formatDateTime(row.starts_at)}
                        </p>
                      </div>
                    </div>
                  </EducationalCard>
                ))}
              </div>
            </div>
          )}

          {/* Recent activity */}
          {data.recent_activity.length > 0 && (
            <div className="space-y-3 animate-stagger-5">
              <SectionHeading
                title="Recent activity"
                actions={
                  <Link href="/announcements" className="text-small font-medium text-brand underline underline-offset-2">
                    Announcements
                  </Link>
                }
              />
              <EducationalCard variant="default" className="divide-y divide-line-soft">
                {data.recent_activity.map((row) => (
                  <div key={row.id} className="flex items-start gap-3 p-4 first:pt-4 last:pb-4">
                    <History className="mt-0.5 h-4 w-4 shrink-0 text-ink-faint" aria-hidden />
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-body text-ink">{row.summary || row.action}</p>
                      <p className="truncate text-caption text-ink-muted">
                        {row.actor}
                        {row.actor_role ? ` · ${row.actor_role}` : ""} · {formatDateTime(row.created_at)}
                      </p>
                    </div>
                  </div>
                ))}
              </EducationalCard>
            </div>
          )}

          {openItems === 0 && (
            <EducationalCard variant="elevated">
              <StatCard
                label="Nothing waiting"
                value="All clear"
                hint="No papers, results, timetable changes or requests need a decision."
                trend="Queues are empty"
                trendUp
                icon={<CalendarDays className="h-5 w-5" />}
                iconColor="success"
              />
            </EducationalCard>
          )}
        </PageStack>
      </PageTransitionWrapper>
    </>
  );
}

/* -------------------------------------------------------------------------- */
/* Pieces                                                                      */
/* -------------------------------------------------------------------------- */

function QueueStat({
  label,
  value,
  hint,
  icon,
  href,
}: {
  label: string;
  value: number;
  hint: string;
  icon: React.ReactNode;
  href: string;
}) {
  return (
    <Link href={href} className="group">
      {/* The StatCard owns the icon so the card renders exactly one glyph —
          a second slot on the wrapper would stack two copies at top-right. */}
      <EducationalCard variant="elevated">
        <StatCard
          label={label}
          value={value}
          hint={hint}
          trend={value > 0 ? "Waiting on you" : "All clear"}
          trendUp={value === 0}
          icon={icon}
          iconColor={value > 0 ? "warning" : "success"}
        />
      </EducationalCard>
    </Link>
  );
}

function AdminQueue<T>({
  title,
  rows,
  emptyText,
  href,
  hrefLabel,
  render,
}: {
  title: string;
  rows: T[];
  emptyText: string;
  href: string;
  hrefLabel: string;
  render: (row: T) => React.ReactNode;
}) {
  return (
    <div className="space-y-3">
      <SectionHeading
        title={title}
        description={rows.length > 0 ? `${rows.length} waiting` : undefined}
        actions={
          <Link href={href} className="text-small font-medium text-brand underline underline-offset-2">
            {hrefLabel}
          </Link>
        }
      />
      {rows.length === 0 ? (
        <EducationalCard variant="default" className="p-5">
          <p className="text-small text-ink-muted">{emptyText}</p>
        </EducationalCard>
      ) : (
        <ul className="space-y-2">
          {rows.map((row, index) => (
            <li key={index}>
              <EducationalCard variant="default" className="p-4">
                <div className="flex items-start justify-between gap-3">
                  {render(row)}
                </div>
              </EducationalCard>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
