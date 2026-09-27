"use client";

import {
  BookOpen,
  CalendarDays,
  ClipboardList,
  FileStack,
  GraduationCap,
  LayoutDashboard,
  LifeBuoy,
  type LucideIcon,
  Megaphone,
  MessageSquarePlus,
  NotebookPen,
  UserRound,
} from "lucide-react";

import type { Capability } from "@/lib/session-types";

export interface NavItem {
  href: string;
  label: string;
  icon: LucideIcon;
  capability?: Capability;
  description?: string;
}

export interface NavGroup {
  label: string;
  items: NavItem[];
}

/**
 * Navigation is grouped by intent, not by database table. The sidebar stays
 * short enough to scan — the secondary modules (feedback) live under Support
 * rather than crowding the Academics list.
 */
export const navigation: NavGroup[] = [
  {
    label: "Overview",
    items: [
      {
        href: "/dashboard",
        label: "Dashboard",
        icon: LayoutDashboard,
        description: "What you need to know today",
      },
    ],
  },
  {
    label: "Academics",
    items: [
      { href: "/subjects", label: "Subjects", icon: BookOpen, capability: "view_subjects" },
      { href: "/timetable", label: "Timetable", icon: CalendarDays, capability: "view_timetable" },
      { href: "/papers", label: "Papers", icon: FileStack, capability: "view_papers" },
      { href: "/practice", label: "Practice", icon: NotebookPen, capability: "practice_papers" },
      { href: "/results", label: "Results", icon: GraduationCap, capability: "view_results" },
      { href: "/attendance", label: "Attendance", icon: ClipboardList, capability: "view_attendance" },
      { href: "/assignments", label: "Assignments", icon: NotebookPen, capability: "view_assignments" },
      { href: "/resources", label: "Resources", icon: BookOpen, capability: "view_resources" },
    ],
  },
  {
    label: "Communication",
    items: [
      { href: "/announcements", label: "Announcements", icon: Megaphone, capability: "view_announcements" },
      { href: "/notifications", label: "Notifications", icon: MessageSquarePlus, capability: "view_notifications" },
      { href: "/calendar", label: "Calendar", icon: CalendarDays, capability: "view_calendar" },
    ],
  },
  {
    label: "Support",
    items: [
      { href: "/requests", label: "Requests", icon: LifeBuoy, capability: "submit_requests" },
      { href: "/feedback", label: "Feedback", icon: MessageSquarePlus, capability: "submit_feedback" },
    ],
  },
  {
    label: "Account",
    items: [
      { href: "/profile", label: "Profile", icon: UserRound },
      { href: "/class-tools", label: "Class tools", icon: ClipboardList, capability: "submit_timetable" },
    ],
  },
];

/** Bottom navigation on small screens — the five things a student opens daily. */
export const mobileNavigation: NavItem[] = [
  { href: "/dashboard", label: "Home", icon: LayoutDashboard },
  { href: "/papers", label: "Papers", icon: FileStack, capability: "view_papers" },
  { href: "/practice", label: "Practice", icon: NotebookPen, capability: "practice_papers" },
  { href: "/notifications", label: "Alerts", icon: MessageSquarePlus, capability: "view_notifications" },
  { href: "/profile", label: "Profile", icon: UserRound },
];

export function visibleGroups(groups: NavGroup[], can: (c: Capability) => boolean): NavGroup[] {
  return groups
    .map((group) => ({
      ...group,
      items: group.items.filter((item) => !item.capability || can(item.capability)),
    }))
    .filter((group) => group.items.length > 0);
}
