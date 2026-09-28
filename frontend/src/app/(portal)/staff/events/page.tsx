"use client";

import * as React from "react";
import { CalendarDays, Plus } from "lucide-react";

import { StaffPage } from "@/components/staff/staff-page";
import { FilterBar, FilterSelect } from "@/components/ui/filter-bar";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { Dialog, DialogClose, DialogContent } from "@/components/ui/dialog";
import { Field, Input, Select, Textarea } from "@/components/ui/input";
import { SkeletonList } from "@/components/ui/skeleton";
import { ErrorState, EmptyState } from "@/components/ui/states";
import { endpoints } from "@/lib/endpoints";
import { useResource } from "@/lib/hooks/use-resource";
import { useRegisterTransition } from "@/lib/hooks/use-register-transition";
import { formatDate, formatDateTime } from "@/lib/utils";
import type { LookupData } from "@/lib/types";

/**
 * Academic calendar management.
 *
 * Events are the institutional schedule: tests, deadlines, holidays. Creating
 * one is a plain create — unlike announcements, the server does not notify
 * anyone, so there is no audience step to get wrong.
 */

const EVENT_TYPES = [
  { value: "TEST", label: "Test" },
  { value: "DEADLINE", label: "Deadline" },
  { value: "HOLIDAY", label: "Holiday" },
  { value: "MEETING", label: "Meeting" },
  { value: "RESULT", label: "Result day" },
  { value: "TEL_EVENT", label: "TEL event" },
];

/** ``datetime-local`` wants a naive local value, not an ISO instant. */
function toLocalInput(date: Date): string {
  const offset = date.getTimezoneOffset() * 60000;
  return new Date(date.getTime() - offset).toISOString().slice(0, 16);
}

export default function StaffEventsPage() {
  const [campusId, setCampusId] = React.useState("");
  const [composing, setComposing] = React.useState(false);

  const query = React.useMemo(
    () => ({ campus: campusId || undefined }),
    [campusId],
  );

  const { data, error, isLoading, refetch } = useResource(
    (signal) => endpoints.staff.calendar(query, { signal }),
    { deps: [JSON.stringify(query)] },
  );

  const { data: lookups } = useResource<LookupData>((signal) =>
    endpoints.platform.lookups(undefined, { signal }),
  );

  const events = data?.events ?? [];
  const upcoming = events.filter((event) => new Date(event.starts_at) >= new Date());
  const past = events.filter((event) => new Date(event.starts_at) < new Date());

  return (
    <StaffPage
      capability="manage_academic_events"
      title="Calendar events"
      description="Tests, deadlines and holidays across the academic calendar."
      actions={
        <Button type="button" onClick={() => setComposing(true)}>
          <Plus className="h-4 w-4" aria-hidden />
          New event
        </Button>
      }
    >
      <FilterBar activeCount={campusId ? 1 : 0} onReset={() => setCampusId("")}>
        <FilterSelect
          value={campusId}
          onChange={setCampusId}
          options={(lookups?.campuses ?? []).map((campus) => ({
            value: String(campus.id),
            label: campus.name,
          }))}
          label="Campus"
          allLabel="All campuses"
          className="w-64"
        />
      </FilterBar>

      {isLoading ? (
        <SkeletonList rows={5} />
      ) : error ? (
        <ErrorState error={error} onRetry={refetch} />
      ) : events.length === 0 ? (
        <EmptyState
          title="Nothing on the calendar"
          description="Add a test, deadline or holiday so students can plan around it."
          icon={<CalendarDays className="h-5 w-5" aria-hidden />}
        />
      ) : (
        <>
          {upcoming.length > 0 ? (
            <EventList title="Upcoming" events={upcoming} />
          ) : null}
          {past.length > 0 ? <EventList title="Past" events={past} muted /> : null}
        </>
      )}

      <CreateEventDialog
        open={composing}
        onOpenChange={setComposing}
        lookups={lookups}
        onCreated={refetch}
      />
    </StaffPage>
  );
}

function EventList({
  title,
  events,
  muted = false,
}: {
  title: string;
  events: { id: number; title: string; event_type_label: string; starts_at: string; is_all_day: boolean; campus_name: string; subject_name: string }[];
  muted?: boolean;
}) {
  return (
    <div className="space-y-3">
      <h2 className="font-display text-h3 text-ink">{title}</h2>
      <ul className="space-y-2.5">
        {events.map((event) => (
          <li key={event.id}>
            <Card tone={muted ? "muted" : "surface"}>
              <CardContent className="pt-4">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div className="min-w-0 flex-1">
                    <p className="font-medium text-ink">{event.title}</p>
                    <p className="mt-0.5 text-caption text-ink-muted">
                      {event.is_all_day
                        ? formatDate(event.starts_at)
                        : formatDateTime(event.starts_at)}
                      {event.campus_name ? ` · ${event.campus_name}` : ""}
                      {event.subject_name ? ` · ${event.subject_name}` : ""}
                    </p>
                  </div>
                  <Badge tone="neutral">{event.event_type_label}</Badge>
                </div>
              </CardContent>
            </Card>
          </li>
        ))}
      </ul>
    </div>
  );
}

function CreateEventDialog({
  open,
  onOpenChange,
  lookups,
  onCreated,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  lookups: LookupData | null | undefined;
  onCreated: () => void;
}) {
  const [title, setTitle] = React.useState("");
  const [description, setDescription] = React.useState("");
  const [eventType, setEventType] = React.useState("TEST");
  const [startsAt, setStartsAt] = React.useState(() => toLocalInput(new Date()));
  const [endsAt, setEndsAt] = React.useState("");
  const [allDay, setAllDay] = React.useState(false);
  const [campusId, setCampusId] = React.useState("");

  const create = useRegisterTransition({
    successTitle: "Event added",
    run: async () => {
      const form = new FormData();
      form.set("title", title);
      form.set("description", description);
      form.set("event_type", eventType);
      // The field is naive local time; the server makes it aware.
      form.set("starts_at", startsAt);
      if (endsAt) form.set("ends_at", endsAt);
      if (allDay) form.set("is_all_day", "true");
      if (campusId) form.set("campus", campusId);
      return endpoints.staff.createEvent(form);
    },
    describeSuccess: () => "It is now visible on the academic calendar.",
    onSettled: () => {
      onCreated();
      setTitle("");
      setDescription("");
    },
  });

  const canSubmit = title.trim().length > 0 && startsAt.length > 0;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        title="New calendar event"
        description="Students see this on their calendar."
        footer={
          <>
            <DialogClose asChild>
              <Button variant="ghost" type="button">
                Cancel
              </Button>
            </DialogClose>
            <Button
              type="button"
              disabled={!canSubmit || Boolean(create.pendingKey)}
              onClick={async () => {
                const saved = await create.act(0, "CREATE");
                if (saved) onOpenChange(false);
              }}
            >
              {create.pendingKey ? "Saving…" : "Add event"}
            </Button>
          </>
        }
      >
        <div className="space-y-4">
          <Field label="Title" htmlFor="event-title" required>
            <Input
              id="event-title"
              value={title}
              onChange={(event) => setTitle(event.target.value)}
              placeholder="Monthly Test 04 — XI Computer Science"
              maxLength={200}
            />
          </Field>

          <Field label="Description" htmlFor="event-description">
            <Textarea
              id="event-description"
              value={description}
              onChange={(event) => setDescription(event.target.value)}
              rows={3}
              placeholder="Optional detail for students."
            />
          </Field>

          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Type" htmlFor="event-type" required>
              <Select
                id="event-type"
                value={eventType}
                onChange={(event) => setEventType(event.target.value)}
              >
                {EVENT_TYPES.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </Select>
            </Field>

            <Field label="Campus" htmlFor="event-campus">
              <Select
                id="event-campus"
                value={campusId}
                onChange={(event) => setCampusId(event.target.value)}
              >
                <option value="">All campuses</option>
                {(lookups?.campuses ?? []).map((campus) => (
                  <option key={campus.id} value={String(campus.id)}>
                    {campus.name}
                  </option>
                ))}
              </Select>
            </Field>

            <Field label="Starts" htmlFor="event-starts" required>
              <Input
                id="event-starts"
                type="datetime-local"
                value={startsAt}
                onChange={(event) => setStartsAt(event.target.value)}
              />
            </Field>

            <Field label="Ends" htmlFor="event-ends" hint="Optional">
              <Input
                id="event-ends"
                type="datetime-local"
                value={endsAt}
                onChange={(event) => setEndsAt(event.target.value)}
              />
            </Field>
          </div>

          <label className="flex items-center gap-2.5 text-small text-ink">
            <input
              type="checkbox"
              checked={allDay}
              onChange={(event) => setAllDay(event.target.checked)}
              className="h-4 w-4 rounded border-line"
            />
            All day
          </label>
        </div>
      </DialogContent>
    </Dialog>
  );
}
