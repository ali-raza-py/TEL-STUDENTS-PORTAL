import Link from "next/link";
import {
  BookOpen,
  Calendar,
  ClipboardList,
  FileText,
  GraduationCap,
  LayoutDashboard,
  TrendingUp,
} from "lucide-react";

import { TelWordmark } from "@/components/layout/wordmark";
import { Button } from "@/components/ui/button";
import { PageTransitionWrapper } from "@/components/education/education-components";

const features = [
  {
    icon: <LayoutDashboard className="h-6 w-6" />,
    title: "Dashboard",
    description: "One unified view of your classes, tasks, and progress.",
    color: "brand",
  },
  {
    icon: <Calendar className="h-6 w-6" />,
    title: "Timetable",
    description: "Your schedule at a glance, synced to your academic calendar.",
    color: "info",
  },
  {
    icon: <ClipboardList className="h-6 w-6" />,
    title: "Practice & Papers",
    description: "Interactive revision tools with intelligent question selection.",
    color: "success",
  },
  {
    icon: <TrendingUp className="h-6 w-6" />,
    title: "Results & Analytics",
    description: "Deep insights into your performance with actionable trends.",
    color: "warning",
  },
  {
    icon: <FileText className="h-6 w-6" />,
    title: "Attendance",
    description: "Track your attendance and stay on top of requirements.",
    color: "danger",
  },
  {
    icon: <BookOpen className="h-6 w-6" />,
    title: "Resources",
    description: "Access course materials, lecture notes, and reading lists.",
    color: "lilac",
  },
];

export default function HomePage() {
  return (
    <>
      <div className="relative z-10 mx-auto min-h-dvh">
        {/* Hero */}
        <header className="flex flex-col items-center pt-12 pb-8 sm:pt-16 sm:pb-12">
          <PageTransitionWrapper>
            <TelWordmark size="lg" className="mb-2" />
            <h1 className="font-display text-display text-center font-semibold text-ink leading-[1.08] tracking-tight">
              Your learning, in one clear view.
            </h1>
            <p className="mt-5 max-w-2xl text-center text-body-lg text-ink-muted">
              The TEL Education Link student portal brings your timetable,
              attendance, assessments, and academic progress together in one
              focused, beautifully designed space.
            </p>
          </PageTransitionWrapper>

          <div className="mt-10 flex flex-wrap items-center justify-center gap-4">
            <Link href="/login" className="animate-fade-in-up animate-stagger-1">
              <Button
                size="lg"
                variant="primary"
                icon={<GraduationCap className="h-5 w-5" />}
                className="shadow-raised"
              >
                Sign in to the portal
              </Button>
            </Link>
          </div>
        </header>

        {/* Features */}
        <main className="mx-auto max-w-5xl px-4 pb-24 sm:px-6">
          <SectionHeading
            title="Everything you need for success"
            subtitle="Six core tools, all integrated into one intelligent portal."
          />
          <div className="mt-12 grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
            {features.map((feature, i) => (
              <FeatureCard
                key={feature.title}
                feature={feature}
                delay={i + 1}
              />
            ))}
          </div>
        </main>

        {/* Footer */}
        <footer className="mx-auto max-w-5xl px-4 pb-10 text-center text-small text-ink-faint sm:px-6">
          <p className="flex items-center justify-center gap-2">
            <span>© {new Date().getFullYear()} TEL Education Link</span>
            <span aria-hidden>|</span>
            <span>Student Portal</span>
          </p>
        </footer>
      </div>
    </>
  );
}

function SectionHeading({
  title,
  subtitle,
}: {
  title: string;
  subtitle?: string;
}) {
  return (
    <div className="text-center">
      <h2 className="font-display text-h2 font-semibold text-ink">
        {title}
      </h2>
      {subtitle ? (
        <p className="mt-3 max-w-xl text-center text-body text-ink-muted">
          {subtitle}
        </p>
      ) : null}
    </div>
  );
}

const iconColorClasses: Record<string, string> = {
  brand: "bg-brand-tint text-brand",
  info: "bg-info-soft text-info",
  success: "bg-success-soft text-success",
  warning: "bg-warning-soft text-warning",
  danger: "bg-danger-soft text-danger",
  lilac: "bg-subject-lilac-soft text-subject-lilac",
};

function FeatureCard({
  feature,
  delay,
}: {
  feature: (typeof features)[number];
  delay: number;
}) {
  return (
    <div
      className="rounded-card border border-line bg-surface p-6 shadow-hairline"
      style={{ animationDelay: `${delay * 0.08}s` }}
    >
      <div
        className={
          "mb-4 flex h-12 w-12 items-center justify-center rounded-xl" +
          ` ${iconColorClasses[feature.color]}`
        }
      >
        {feature.icon}
      </div>
      <h3 className="font-display text-h3 font-semibold text-ink">
        {feature.title}
      </h3>
      <p className="mt-2 text-body text-ink-muted">
        {feature.description}
      </p>
    </div>
  );
}
