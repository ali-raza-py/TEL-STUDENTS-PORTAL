"use client";

import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";
import { Loader2 } from "lucide-react";
import * as React from "react";

import { cn } from "@/lib/utils";

/**
 * The single button in the product. Sizes, tones and states are declared once
 * here so no page invents its own padding or focus ring.
 */

const buttonVariants = cva(
  [
    "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-control",
    /* Slightly tighter than body text so labels sit as UI, not prose. */
    "font-semibold tracking-[-0.005em]",
    "transition-[background-color,color,box-shadow,transform,border-color] duration-200",
    "disabled:pointer-events-none disabled:opacity-[var(--opacity-disabled)] select-none",
    "active:translate-y-px",
    "[&_svg]:shrink-0",
  ],
  {
    variants: {
      variant: {
        primary:
          "bg-brand text-white shadow-[var(--shadow-hairline)] hover:bg-brand-deep hover:shadow-[var(--shadow-soft)] focus-visible:outline-brand",
        secondary:
          "bg-surface text-ink border border-line shadow-[var(--shadow-hairline)] hover:bg-surface-muted hover:border-line-strong",
        soft: "bg-brand-tint text-brand-deep hover:bg-brand-soft",
        ghost: "text-ink-soft hover:bg-surface-muted hover:text-ink",
        danger:
          "bg-danger text-white shadow-[var(--shadow-hairline)] hover:brightness-95",
        quiet: "text-ink-muted hover:text-ink hover:bg-surface-muted",
        link: "text-brand underline-offset-4 hover:underline px-0 h-auto",
      },
      size: {
        sm: "h-8 px-3 text-small",
        md: "h-10 px-4 text-[0.875rem]",
        lg: "h-12 px-6 text-[0.9375rem]",
        icon: "h-10 w-10",
        iconSm: "h-8 w-8",
      },
      block: { true: "w-full", false: "" },
    },
    defaultVariants: { variant: "primary", size: "md", block: false },
  },
);

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean;
  loading?: boolean;
  /** Rendered before the label; hidden while loading. */
  icon?: React.ReactNode;
}

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  { className, variant, size, block, asChild = false, loading = false, icon, children, disabled, ...props },
  ref,
) {
  const content = loading ? (
    <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
  ) : (
    icon
  );

  // Radix Slot accepts exactly one React element. When a Button renders as a
  // link, merge its icon/loading indicator into that link instead of passing
  // it as a sibling. This keeps link-buttons with badges or labels valid.
  //
  // A link has no `disabled` attribute, so an inactive link-button is marked
  // `aria-disabled` and taken out of the tab order instead — otherwise a
  // loading link-button would still be focusable and clickable.
  if (asChild) {
    const child = React.Children.only(children) as React.ReactElement<{
      children?: React.ReactNode;
    }>;
    const inactive = Boolean(disabled || loading);
    return (
      <Slot
        ref={ref}
        className={cn(
          buttonVariants({ variant, size, block }),
          inactive && "pointer-events-none opacity-55",
          className,
        )}
        aria-disabled={inactive || undefined}
        aria-busy={loading || undefined}
        tabIndex={inactive ? -1 : undefined}
        {...props}
      >
        {React.cloneElement(child, undefined, <>{content}{child.props.children}</>)}
      </Slot>
    );
  }

  const Comp = "button";
  return (
    <Comp
      ref={ref}
      className={cn(buttonVariants({ variant, size, block }), className)}
      disabled={disabled || loading}
      aria-busy={loading || undefined}
      {...props}
    >
      {content}
      {children}
    </Comp>
  );
});

export { buttonVariants };
