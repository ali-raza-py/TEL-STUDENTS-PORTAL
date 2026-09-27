"use client";

import * as React from "react";
import { BookOpen, GraduationCap, Award, Target, Lightbulb, Globe } from "lucide-react";

import { cn } from "@/lib/utils";

const floatingElements = [
  { icon: BookOpen, color: "bg-brand-tint", top: "5%", left: "3%", delay: "0s", size: 48 },
  { icon: GraduationCap, color: "bg-success-soft", top: "15%", right: "5%", delay: "2s", size: 40 },
  { icon: Award, color: "bg-warning-soft", top: "30%", left: "2%", delay: "4s", size: 36 },
  { icon: Target, color: "bg-info-soft", bottom: "20%", right: "3%", delay: "1s", size: 44 },
  { icon: Lightbulb, color: "bg-danger-soft", bottom: "10%", left: "5%", delay: "3s", size: 42 },
  { icon: Globe, color: "bg-brand-soft", top: "50%", left: "50%", delay: "5s", size: 38 },
];

export function FloatingEducationBackground({
  className,
  opacity = 0.05,
}: {
  className?: string;
  opacity?: number;
}) {
  return (
    <div
      className={cn(
        "pointer-events-none fixed inset-0 overflow-hidden z-0",
        className,
      )}
      aria-hidden="true"
    >
      {floatingElements.map(({ icon: Icon, color, top, right, bottom, left, delay, size }, i) => (
        <div
          key={i}
          className={cn(
            "absolute rounded-2xl shadow-2xl animate-float",
            color,
          )}
          style={{
            opacity,
            animationDelay: delay,
            width: size,
            height: size,
            top,
            right,
            bottom,
            left,
          }}
        >
          <Icon className="w-full h-full text-current opacity-50" aria-hidden />
          <div
            className="absolute inset-0 rounded-2xl"
            style={{
              boxShadow:
                "inset 0 0 0 1px rgba(255,255,255,0.4), 0 0 12px 2px rgba(47,107,79,0.15)",
            }}
          />
        </div>
      ))}
    </div>
  );
}

export function FloatingOrbs({
  className,
  count = 5,
  color = "brand",
  opacity = 0.04,
}: {
  className?: string;
  count?: number;
  color?: "brand" | "success" | "warning" | "danger" | "info" | "lilac" | "mint";
  opacity?: number;
}) {
  const colorClasses = {
    brand: "bg-brand-tint",
    success: "bg-success-soft",
    warning: "bg-warning-soft",
    danger: "bg-danger-soft",
    info: "bg-info-soft",
    lilac: "bg-subject-lilac-soft",
    mint: "bg-subject-mint-soft",
  };

  const glowRgb = {
    brand: "47, 107, 79",
    success: "44, 122, 85",
    warning: "154, 107, 31",
    danger: "157, 59, 44",
    info: "53, 98, 127",
    lilac: "95, 90, 134",
    mint: "59, 127, 107",
  };

  return (
    <div
      className={cn("pointer-events-none absolute inset-0 overflow-hidden z-0 rounded-panel", className)}
      aria-hidden="true"
    >
      {Array.from({ length: count }).map((_, i) => {
        const size = 40 + (i * 50) % 160;
        const delay = i * 2;
        const duration = 20 + i * 5;
        return (
          <div
            key={i}
            className={cn(
              "absolute rounded-full animate-blob blur-[1px]",
              colorClasses[color],
            )}
            style={{
              opacity,
              width: size,
              height: size,
              top: `${(i * 19) % 75}%`,
              left: `${(i * 27) % 75}%`,
              animationDelay: `${delay}s`,
              animationDuration: `${duration}s`,
              boxShadow: `0 0 20px 6px rgba(${glowRgb[color]}, 0.18)`,
            }}
          />
        );
      })}
    </div>
  );
}

export function PageTransitionWrapper({
  children,
  className,
  delay = 0,
}: {
  children: React.ReactNode;
  className?: string;
  delay?: number;
}) {
  return (
    <div
      className={cn("animate-fade-in-up", className)}
      style={delay ? { animationDelay: `${delay}s` } : undefined}
    >
      {children}
    </div>
  );
}

export function EducationalCard({
  children,
  icon,
  iconColor = "brand",
  className,
  variant = "default",
  hover = true,
}: {
  children: React.ReactNode;
  icon?: React.ReactNode;
  iconColor?: "brand" | "success" | "warning" | "danger" | "info" | "lilac" | "mint";
  className?: string;
  variant?: "default" | "elevated" | "glass" | "3d";
  hover?: boolean;
}) {
  const variants = {
    default: cn(
      "bg-surface border border-line shadow-soft",
      hover && "transition-all duration-300 hover:shadow-raised",
    ),
    elevated: cn(
      "bg-surface border border-line shadow-raised",
      hover && "transition-all duration-300 hover:shadow-overlay hover:-translate-y-1",
    ),
    glass:
      "bg-surface/70 backdrop-blur-xl border border-line-soft/50 shadow-soft",
    "3d":
      "bg-surface border border-line shadow-raised transform-gpu transform-style-preserve-3d",
  };

  const iconColors = {
    brand: "bg-brand-tint text-brand",
    success: "bg-success-soft text-success",
    warning: "bg-warning-soft text-warning",
    danger: "bg-danger-soft text-danger",
    info: "bg-info-soft text-info",
    lilac: "bg-subject-lilac-soft text-subject-lilac",
    mint: "bg-subject-mint-soft text-subject-mint",
  };

  return (
    <div
      className={cn(
        "rounded-2xl p-6",
        variants[variant],
        hover && variant !== "glass" && "card-3d",
        className,
      )}
    >
      {icon && (
        <div
          className={cn(
            "inline-flex items-center justify-center w-12 h-12 rounded-xl mb-4",
            iconColors[iconColor],
          )}
        >
          {icon}
        </div>
      )}
      {children}
    </div>
  );
}

export function StatCard({
  label,
  value,
  trend,
  trendUp = true,
  icon,
  iconColor = "brand",
  className,
  hint,
}: {
  label: string;
  value: React.ReactNode;
  trend?: string;
  trendUp?: boolean;
  icon?: React.ReactNode;
  iconColor?: "brand" | "success" | "warning" | "danger" | "info" | "lilac" | "mint";
  className?: string;
  hint?: string;
}) {
  const iconColors = {
    brand: "bg-brand-tint text-brand",
    success: "bg-success-soft text-success",
    warning: "bg-warning-soft text-warning",
    danger: "bg-danger-soft text-danger",
    info: "bg-info-soft text-info",
    lilac: "bg-subject-lilac-soft text-subject-lilac",
    mint: "bg-subject-mint-soft text-subject-mint",
  };

  return (
    <EducationalCard className={cn("h-full", className)} variant="glass">
      <div className="flex items-start justify-between">
        <div>
          <p className="text-caption font-semibold uppercase tracking-[0.08em] text-ink-faint">
            {label}
          </p>
          <p className="mt-2 font-display text-3xl tabular-nums text-ink">
            {value}
          </p>
          {hint && <p className="mt-1 text-sm text-ink-muted">{hint}</p>}
        </div>
        {icon && (
          <div className={cn("w-12 h-12 rounded-xl flex items-center justify-center", iconColors[iconColor])}>
            {icon}
          </div>
        )}
      </div>
      {trend && (
        <div
          className={cn(
            "mt-4 flex items-center gap-1.5 text-sm",
            trendUp ? "text-success" : "text-danger",
          )}
        >
          <span className="font-medium">{trend}</span>
          <span className="text-ink-muted">vs last period</span>
        </div>
      )}
    </EducationalCard>
  );
}

export function SubjectPill({
  children,
  color = "sage",
  size = "md",
  className,
}: {
  children: React.ReactNode;
  color?: "sage" | "mint" | "sky" | "sand" | "clay" | "lilac";
  size?: "sm" | "md" | "lg";
  className?: string;
}) {
  const colors = {
    sage: "bg-subject-sage-soft text-subject-sage border-subject-sage/30",
    mint: "bg-subject-mint-soft text-subject-mint border-subject-mint/30",
    sky: "bg-subject-sky-soft text-subject-sky border-subject-sky/30",
    sand: "bg-subject-sand-soft text-subject-sand border-subject-sand/30",
    clay: "bg-subject-clay-soft text-subject-clay border-subject-clay/30",
    lilac: "bg-subject-lilac-soft text-subject-lilac border-subject-lilac/30",
  };

  const sizes = {
    sm: "px-2.5 py-0.5 text-xs",
    md: "px-3 py-1 text-sm",
    lg: "px-4 py-1.5 text-base",
  };

  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border font-medium",
        "transition-colors duration-200",
        colors[color],
        sizes[size],
        className,
      )}
    >
      {children}
    </span>
  );
}

export function ProgressRingAnimated({
  value,
  size = 80,
  strokeWidth = 8,
  color = "brand",
  className,
  children,
}: {
  value: number | null;
  size?: number;
  strokeWidth?: number;
  color?: "brand" | "success" | "warning" | "danger";
  className?: string;
  children?: React.ReactNode;
}) {
  const colors = {
    brand: "stroke-brand",
    success: "stroke-success",
    warning: "stroke-warning",
    danger: "stroke-danger",
  };

  const radius = (size - strokeWidth) / 2;
  const circumference = 2 * Math.PI * radius;
  const clamped = value === null ? 0 : Math.max(0, Math.min(100, value));
  const offset = circumference - (clamped / 100) * circumference;

  return (
    <div
      className={cn("relative inline-flex items-center justify-center", className)}
      style={{ width: size, height: size }}
      role="img"
      aria-label={value === null ? "No data" : `${Math.round(clamped)} percent`}
    >
      <svg width={size} height={size} className="-rotate-90" aria-hidden>
        <defs>
          <linearGradient id={`grad-${color}`} x1="0%" y1="0%" x2="100%" y2="0%">
            <stop offset="0%" stopColor="rgba(47,107,79,0.15)" />
            <stop offset="100%" stopColor="rgba(47,107,79,0.45)" />
          </linearGradient>
        </defs>
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          strokeWidth={strokeWidth}
          className="stroke-surface-sunken"
        />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          strokeWidth={strokeWidth}
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          className={cn(
            "transition-all duration-1000 ease-out",
            colors[color],
          )}
          style={{
            strokeDashoffset: offset,
            stroke:
              color === "brand"
                ? "url(#grad-brand)"
                : undefined,
          }}
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        {children ?? (
          <span className="font-display text-2xl tabular-nums text-ink">
            {value === null ? "—" : `${Math.round(clamped)}%`}
          </span>
        )}
      </div>
    </div>
  );
}
