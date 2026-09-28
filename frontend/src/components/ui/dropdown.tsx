"use client";

import * as DropdownMenu from "@radix-ui/react-dropdown-menu";
import { Check } from "lucide-react";
import * as React from "react";

import { cn } from "@/lib/utils";

export const Dropdown = DropdownMenu.Root;
export const DropdownTrigger = DropdownMenu.Trigger;

export function DropdownContent({
  className,
  align = "end",
  sideOffset = 6,
  children,
  ...props
}: React.ComponentPropsWithoutRef<typeof DropdownMenu.Content>) {
  return (
    <DropdownMenu.Portal>
      <DropdownMenu.Content
        align={align}
        sideOffset={sideOffset}
        className={cn(
          "animate-scale-in z-50 min-w-[12rem] overflow-hidden rounded-panel border border-line bg-surface p-1.5 shadow-[var(--shadow-overlay)]",
          className,
        )}
        {...props}
      >
        {children}
      </DropdownMenu.Content>
    </DropdownMenu.Portal>
  );
}

export function DropdownItem({
  className,
  children,
  ...props
}: React.ComponentPropsWithoutRef<typeof DropdownMenu.Item>) {
  return (
    <DropdownMenu.Item
      className={cn(
        "flex cursor-pointer select-none items-center gap-2.5 rounded-control px-3 py-2 text-small text-ink-soft outline-none",
        "transition-colors duration-150 hover:bg-surface-muted hover:text-ink data-[highlighted]:bg-surface-muted data-[highlighted]:text-ink",
        "data-[disabled]:pointer-events-none data-[disabled]:opacity-50",
        className,
      )}
      {...props}
    >
      {children}
    </DropdownMenu.Item>
  );
}

export function DropdownLabel({ className, ...props }: React.ComponentPropsWithoutRef<typeof DropdownMenu.Label>) {
  return (
    <DropdownMenu.Label
      className={cn("px-3 py-1.5 text-label font-bold uppercase text-ink-faint", className)}
      {...props}
    />
  );
}

export function DropdownSeparator({ className }: { className?: string }) {
  return <DropdownMenu.Separator className={cn("my-1.5 h-px bg-line-soft", className)} />;
}

export function DropdownCheckboxItem({
  checked,
  children,
  className,
  ...props
}: React.ComponentPropsWithoutRef<typeof DropdownMenu.CheckboxItem>) {
  return (
    <DropdownMenu.CheckboxItem
      checked={checked}
      className={cn(
        "flex cursor-pointer select-none items-center gap-2.5 rounded-control px-3 py-2 text-small text-ink-soft outline-none hover:bg-surface-muted",
        className,
      )}
      {...props}
    >
      <span className="flex h-4 w-4 items-center justify-center rounded-[4px] border border-line-strong">
        <DropdownMenu.ItemIndicator>
          <Check className="h-3 w-3 text-brand" aria-hidden />
        </DropdownMenu.ItemIndicator>
      </span>
      {children}
    </DropdownMenu.CheckboxItem>
  );
}
