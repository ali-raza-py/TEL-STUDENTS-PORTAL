"use client";

import { useState } from "react";
import Link from "next/link";
import { Pin } from "lucide-react";

import { PageHeader, PageStack, SectionHeading } from "@/components/ui/page-header";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card";
import { Badge, ToneBadge } from "@/components/ui/badge";
import { Pagination } from "@/components/ui/tabs";
import { SkeletonPage, SkeletonList } from "@/components/ui/skeleton";
import { EmptyState, ErrorState } from "@/components/ui/states";
import { SearchInput } from "@/components/ui/filter-bar";
import { formatDate, formatRelative, cn } from "@/lib/utils";
import { useResource, useDebounced } from "@/lib/hooks/use-resource";
import { endpoints } from "@/lib/endpoints";
import type { AnnouncementRow } from "@/lib/types";
import { FloatingOrbs, PageTransitionWrapper } from "@/components/education/education-components";

export default function AnnouncementsPage() {
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);

  const debouncedSearch = useDebounced(search, 320);

  const { data, error, isLoading, refetch } = useResource(
    (signal) => endpoints.engagement.announcements({ page, search: debouncedSearch } as Record<string, string | number | boolean | null | undefined>, { signal }),
    { deps: [page, debouncedSearch] },
  );

  if (isLoading) return <SkeletonPage />;
  if (error) return <ErrorState error={error} onRetry={refetch} />;
  if (!data) return null;

  const announcements = data.results;
  const pinned = announcements.filter((a) => a.is_pinned);
  const others = announcements.filter((a) => !a.is_pinned);

  return (
    <div className="relative min-h-[calc(100dvh-4rem)]">
      <FloatingOrbs opacity={0.04} color="brand" count={4} />
      <PageTransitionWrapper>
        <PageStack>
          <PageHeader title="Announcements" description="Important updates from your school." />

      <SearchInput
        value={search}
        onChange={(v) => { setSearch(v); setPage(1); }}
        placeholder="Search announcements…"
        className="max-w-sm"
      />

      {pinned.length > 0 && (
        <>
          <SectionHeading title="Pinned" />
          <div className="space-y-3">
            {pinned.map((announcement: AnnouncementRow) => (
              <AnnouncementCard key={announcement.id} announcement={announcement} pinned />
            ))}
          </div>
        </>
      )}

      {others.length > 0 && (
        <>
          {!pinned.length ? null : <SectionHeading title="All announcements" />}
          <div className="space-y-3">
            {others.map((announcement: AnnouncementRow) => (
              <AnnouncementCard key={announcement.id} announcement={announcement} />
            ))}
          </div>
        </>
      )}

      {announcements.length === 0 && (
        <EmptyState title="No announcements" description="There are no announcements to display." />
      )}

      {data && data.count > 0 && (
        <Pagination
          page={data.page}
          numPages={data.num_pages}
          hasNext={data.has_next}
          hasPrevious={data.has_previous}
          onChange={setPage}
          label="Announcements navigation"
        />
      )}
    </PageStack>
    </PageTransitionWrapper>
    </div>
  );
}

function AnnouncementCard({
  announcement,
  pinned,
}: {
  announcement: AnnouncementRow;
  pinned?: boolean;
}) {
  const bodyText = announcement.body.length > 200
    ? announcement.body.slice(0, 200) + "..."
    : announcement.body;

  return (
    <Link href={`/announcements/${announcement.id}`}>
      <Card className={cn("group p-5 transition-transform hover:scale-[1.01]", pinned && "border-brand-soft bg-brand-tint/30")}>
        <CardHeader>
          <div className="flex items-start justify-between gap-2">
            <CardTitle className="flex items-center gap-2">
              {pinned && <Pin className="h-4 w-4 text-brand" />}
              {announcement.title}
            </CardTitle>
            <Badge tone={pinned ? "solid" : "neutral"}>
              {pinned ? "Pinned" : formatRelative(announcement.published_at)}
            </Badge>
          </div>
          <CardDescription>
            By {announcement.author_name} · {formatDate(announcement.published_at)}
          </CardDescription>
        </CardHeader>
        {announcement.body && (
          <CardContent>
            <p className="line-clamp-3 text-small text-ink-muted">{bodyText}</p>
          </CardContent>
        )}
      </Card>
    </Link>
  );
}
