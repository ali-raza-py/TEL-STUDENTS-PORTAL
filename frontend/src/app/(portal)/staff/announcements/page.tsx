"use client";

import * as React from "react";
import { Megaphone, Plus } from "lucide-react";

import { StaffPage } from "@/components/staff/staff-page";
import { FilterBar, FilterSelect, SearchInput } from "@/components/ui/filter-bar";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { Dialog, DialogClose, DialogContent } from "@/components/ui/dialog";
import { Field, Input, Select, Textarea } from "@/components/ui/input";
import { Checkbox } from "@/components/ui/input";
import { SkeletonList } from "@/components/ui/skeleton";
import { ErrorState, EmptyState } from "@/components/ui/states";
import { endpoints } from "@/lib/endpoints";
import { useDebounced, useResource } from "@/lib/hooks/use-resource";
import { useRegisterTransition } from "@/lib/hooks/use-register-transition";
import { formatDateTime } from "@/lib/utils";
import type { LookupData } from "@/lib/types";

/**
 * Announcement management.
 *
 * Creating an announcement immediately notifies every student in the chosen
 * audience, so the dialog states the audience it will reach before publishing
 * and the target pickers cascade campus → programme → class → section so the
 * selection cannot be contradictory.
 */

const AUDIENCES = [
  { value: "ALL_STUDENTS", label: "All students" },
  { value: "CAMPUS", label: "One campus" },
  { value: "PROGRAM", label: "One programme" },
  { value: "CLASS", label: "One class" },
  { value: "SECTION", label: "One section" },
];

export default function StaffAnnouncementsPage() {
  const [search, setSearch] = React.useState("");
  const [classId, setClassId] = React.useState("");
  const [composing, setComposing] = React.useState(false);
  const debouncedSearch = useDebounced(search);

  const query = React.useMemo(
    () => ({ search: debouncedSearch || undefined, class: classId || undefined }),
    [debouncedSearch, classId],
  );

  const { data, error, isLoading, refetch } = useResource(
    (signal) => endpoints.staff.announcements(query, { signal }),
    { deps: [JSON.stringify(query)] },
  );

  const { data: lookups } = useResource<LookupData>((signal) =>
    endpoints.platform.lookups(undefined, { signal }),
  );

  const activeCount = (debouncedSearch ? 1 : 0) + (classId ? 1 : 0);
  const rows = data?.results ?? [];

  return (
    <StaffPage
      capability="manage_announcements"
      title="Announcements"
      description="What students are told, and who hears it."
      actions={
        <Button type="button" onClick={() => setComposing(true)}>
          <Plus className="h-4 w-4" aria-hidden />
          New announcement
        </Button>
      }
    >
      <FilterBar
        activeCount={activeCount}
        onReset={() => {
          setSearch("");
          setClassId("");
        }}
      >
        <SearchInput
          value={search}
          onChange={setSearch}
          placeholder="Search announcements"
          className="min-w-56 flex-1"
        />
        <FilterSelect
          value={classId}
          onChange={setClassId}
          options={(lookups?.classes ?? []).map((row) => ({
            value: String(row.id),
            label: row.display_name || row.name,
          }))}
          label="Class"
          allLabel="All classes"
          className="w-64"
        />
      </FilterBar>

      {isLoading ? (
        <SkeletonList rows={5} />
      ) : error ? (
        <ErrorState error={error} onRetry={refetch} />
      ) : rows.length === 0 ? (
        <EmptyState
          title="No announcements yet"
          description="Publish one to notify students straight away."
          icon={<Megaphone className="h-5 w-5" aria-hidden />}
        />
      ) : (
        <ul className="space-y-3">
          {rows.map((row) => (
            <li key={row.id}>
              <Card>
                <CardContent className="pt-4">
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <h3 className="font-display text-h3 text-ink">{row.title}</h3>
                        {row.is_pinned ? <Badge tone="warning">Pinned</Badge> : null}
                      </div>
                      <p className="mt-1.5 whitespace-pre-line text-small text-ink-muted">{row.body}</p>
                    </div>
                    <div className="flex shrink-0 flex-col items-end gap-1.5">
                      <Badge tone="brand">{row.audience_label}</Badge>
                      <span className="text-caption text-ink-faint">
                        {formatDateTime(row.published_at)}
                      </span>
                    </div>
                  </div>
                  <p className="mt-3 text-caption text-ink-faint">
                    {[row.campus_name, row.program_name, row.class_name, row.section_name]
                      .filter(Boolean)
                      .join(" · ") || "Everyone"}
                    {row.author_name ? ` · ${row.author_name}` : ""}
                  </p>
                </CardContent>
              </Card>
            </li>
          ))}
        </ul>
      )}

      <ComposeDialog
        open={composing}
        onOpenChange={setComposing}
        lookups={lookups}
        onPublished={refetch}
      />
    </StaffPage>
  );
}

function ComposeDialog({
  open,
  onOpenChange,
  lookups,
  onPublished,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  lookups: LookupData | null | undefined;
  onPublished: () => void;
}) {
  const [title, setTitle] = React.useState("");  const [body, setBody] = React.useState("");
  const [audience, setAudience] = React.useState("ALL_STUDENTS");
  const [campusId, setCampusId] = React.useState("");
  const [programId, setProgramId] = React.useState("");
  const [classId, setClassId] = React.useState("");
  const [sectionId, setSectionId] = React.useState("");
  const [pinned, setPinned] = React.useState(false);

  // Programmes are institution-wide, so the narrowing cascade runs
  // campus → class → section, with programme only further restricting the class.
  const programs = lookups?.programs ?? [];
  const classes = (lookups?.classes ?? []).filter((row) => {
    if (campusId && row.campus_id !== undefined && String(row.campus_id) !== campusId) return false;
    if (programId && row.program_id !== undefined && String(row.program_id) !== programId) return false;
    return true;
  });
  const sections = (lookups?.sections ?? []).filter(
    (section) => !classId || String(section.class_id) === classId,
  );

  const submit = useRegisterTransition({
    successTitle: "Announcement published",
    run: async () => {
      const form = new FormData();
      form.set("title", title);
      form.set("body", body);
      form.set("audience", audience);
      if (audience !== "ALL_STUDENTS" && campusId) form.set("campus", campusId);
      if (audience === "PROGRAM" || audience === "CLASS" || audience === "SECTION") {
        if (programId) form.set("program", programId);
      }
      if (audience === "CLASS" || audience === "SECTION") {
        if (classId) form.set("class_room", classId);
      }
      if (audience === "SECTION" && sectionId) form.set("section", sectionId);
      if (pinned) form.set("is_pinned", "true");
      return endpoints.staff.publishAnnouncement(form);
    },
    describeSuccess: () => "Students in the audience have been notified.",
    onSettled: () => {
      onPublished();
      setTitle("");
      setBody("");
      setPinned(false);
    },
  });

  const needsTarget = audience !== "ALL_STUDENTS";
  const canSubmit = title.trim() && body.trim() && (!needsTarget || campusId);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        title="New announcement"
        description="Publishing notifies every student in the audience immediately."
        size="lg"
        footer={
          <>
            <DialogClose asChild>
              <Button variant="ghost" type="button">
                Cancel
              </Button>
            </DialogClose>
            <Button
              type="button"
              disabled={!canSubmit || Boolean(submit.pendingKey)}
              onClick={async () => {
                const saved = await submit.act(0, "PUBLISH");
                if (saved) onOpenChange(false);
              }}
            >
              {submit.pendingKey ? "Publishing…" : "Publish"}
            </Button>
          </>
        }
      >
        <div className="space-y-4">
          <Field label="Title" htmlFor="ann-title" required>
            <Input
              id="ann-title"
              value={title}
              onChange={(event) => setTitle(event.target.value)}
              placeholder="Short headline students will scan"
              maxLength={200}
            />
          </Field>

          <Field label="Message" htmlFor="ann-body" required>
            <Textarea
              id="ann-body"
              value={body}
              onChange={(event) => setBody(event.target.value)}
              rows={5}
              placeholder="What students need to know, and any action they must take."
            />
          </Field>

          <Field label="Audience" htmlFor="ann-audience" required>
            <Select
              id="ann-audience"
              value={audience}
              onChange={(event) => {
                setAudience(event.target.value);
                setProgramId("");
                setClassId("");
                setSectionId("");
              }}
            >
              {AUDIENCES.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </Select>
          </Field>

          {needsTarget ? (
            <div className="grid gap-4 sm:grid-cols-2">
              <Field label="Campus" htmlFor="ann-campus" required>
                <Select
                  id="ann-campus"
                  value={campusId}
                  onChange={(event) => {
                    setCampusId(event.target.value);
                    setProgramId("");
                    setClassId("");
                    setSectionId("");
                  }}
                >
                  <option value="">Choose a campus</option>
                  {(lookups?.campuses ?? []).map((campus) => (
                    <option key={campus.id} value={String(campus.id)}>
                      {campus.name}
                    </option>
                  ))}
                </Select>
              </Field>

              {audience !== "CAMPUS" ? (
                <Field label="Programme" htmlFor="ann-program" required={audience === "PROGRAM"}>
                  <Select
                    id="ann-program"
                    value={programId}
                    onChange={(event) => {
                      setProgramId(event.target.value);
                      setClassId("");
                      setSectionId("");
                    }}
                  >
                    <option value="">Choose a programme</option>
                    {programs.map((program) => (
                      <option key={program.id} value={String(program.id)}>
                        {program.name}
                      </option>
                    ))}
                  </Select>
                </Field>
              ) : null}

              {audience === "CLASS" || audience === "SECTION" ? (
                <Field label="Class" htmlFor="ann-class" required>
                  <Select
                    id="ann-class"
                    value={classId}
                    onChange={(event) => {
                      setClassId(event.target.value);
                      setSectionId("");
                    }}
                  >
                    <option value="">Choose a class</option>
                    {classes.map((row) => (
                      <option key={row.id} value={String(row.id)}>
                        {row.display_name || row.name}
                      </option>
                    ))}
                  </Select>
                </Field>
              ) : null}

              {audience === "SECTION" ? (
                <Field label="Section" htmlFor="ann-section" required>
                  <Select
                    id="ann-section"
                    value={sectionId}
                    onChange={(event) => setSectionId(event.target.value)}
                  >
                    <option value="">Choose a section</option>
                    {sections.map((section) => (
                      <option key={section.id} value={String(section.id)}>
                        {section.name}
                      </option>
                    ))}
                  </Select>
                </Field>
              ) : null}
            </div>
          ) : null}

          <label className="flex items-center gap-2.5 text-small text-ink">
            <Checkbox checked={pinned} onChange={(event) => setPinned(event.target.checked)} />
            Pin this announcement to the top of the list
          </label>

          {needsTarget && !campusId ? (
            <p className="text-caption text-ink-muted">Choose a campus to see the narrower targets.</p>
          ) : null}
        </div>
      </DialogContent>
    </Dialog>
  );
}
