import { cva, type VariantProps } from "class-variance-authority";
import * as React from "react";

import { cn, type Tone } from "@/lib/utils";

const badgeVariants = cva(
  "inline-flex items-center gap-1.5 rounded-pill border px-2.5 py-1 text-caption font-semibold uppercase tracking-[0.06em]",
  {
    variants: {
      tone: {
        brand: "border-brand-soft bg-brand-tint text-brand-deep",
        success: "border-success-soft bg-success-soft text-success",
        warning: "border-warning-soft bg-warning-soft text-warning",
        danger: "border-danger-soft bg-danger-soft text-danger",
        info: "border-info-soft bg-info-soft text-info",
        neutral: "border-line bg-surface-muted text-ink-soft",
        solid: "border-transparent bg-brand text-white",
      },
      size: { sm: "px-2 py-0.5 text-[0.625rem]", md: "" },
    },
    defaultVariants: { tone: "neutral", size: "md" },
  },
);

export interface BadgeProps
  extends React.HTMLAttributes<HTMLSpanElement>,
    VariantProps<typeof badgeVariants> {
  /** Leading colour swatch — used so status is not communicated by colour alone. */
  dot?: boolean;
}

export function Badge({ className, tone, size, dot = false, children, ...props }: BadgeProps) {
  return (
    <span className={cn(badgeVariants({ tone, size }), className)} {...props}>
      {dot ? <span className="h-1.5 w-1.5 rounded-full bg-current opacity-70" aria-hidden /> : null}
      {children}
    </span>
  );
}

/** Maps a semantic tone onto a badge. */
export function ToneBadge({
  tone,
  children,
  className,
  dot = true,
}: {
  tone: Tone;
  children: React.ReactNode;
  className?: string;
  dot?: boolean;
}) {
  return (
    <Badge tone={tone} dot={dot} className={className}>
      {children}
    </Badge>
  );
}
