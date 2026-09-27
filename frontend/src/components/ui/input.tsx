import * as React from "react";

import { cn } from "@/lib/utils";

export interface FieldProps {
  label: string;
  htmlFor?: string;
  hint?: React.ReactNode;
  error?: string | string[] | null;
  required?: boolean;
  className?: string;
  children: React.ReactNode;
}

export function Field({ label, htmlFor, hint, error, required, className, children }: FieldProps) {
  const messages = Array.isArray(error) ? error : error ? [error] : [];
  return (
    <div className={cn("flex flex-col gap-1.5", className)}>
      <label
        htmlFor={htmlFor}
        className="text-small font-medium text-ink-soft"
      >
        {label}
        {required ? <span className="ml-1 text-danger">*</span> : null}
      </label>
      {children}
      {messages.length > 0 ? (
        <p role="alert" className="text-caption font-medium text-danger">
          {messages.join(" ")}
        </p>
      ) : hint ? (
        <p className="text-caption text-ink-faint">{hint}</p>
      ) : null}
    </div>
  );
}

const controlBase = [
  "w-full rounded-control border bg-surface px-3.5 text-body text-ink",
  "placeholder:text-ink-faint",
  "transition-[border-color,box-shadow] duration-200",
  "focus:outline-none focus-visible:border-brand focus-visible:shadow-focus",
  "disabled:cursor-not-allowed disabled:bg-surface-muted disabled:text-ink-faint",
  "aria-[invalid=true]:border-danger aria-[invalid=true]:shadow-none",
].join(" ");

export interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  invalid?: boolean;
  leading?: React.ReactNode;
  trailing?: React.ReactNode;
}

export const Input = React.forwardRef<HTMLInputElement, InputProps>(function Input(
  { className, invalid, leading, trailing, ...props },
  ref,
) {
  const field = (
    <input
      ref={ref}
      aria-invalid={invalid || undefined}
      className={cn(controlBase, "h-10", leading && "pl-10", trailing && "pr-10", className)}
      {...props}
    />
  );
  if (!leading && !trailing) return field;
  return (
    <div className="relative">
      {leading ? (
        <span className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-ink-faint">
          {leading}
        </span>
      ) : null}
      {field}
      {trailing ? (
        <span className="absolute right-3 top-1/2 -translate-y-1/2 text-ink-faint">{trailing}</span>
      ) : null}
    </div>
  );
});

export const Textarea = React.forwardRef<
  HTMLTextAreaElement,
  React.TextareaHTMLAttributes<HTMLTextAreaElement> & { invalid?: boolean }
>(function Textarea({ className, invalid, rows = 4, ...props }, ref) {
  return (
    <textarea
      ref={ref}
      rows={rows}
      aria-invalid={invalid || undefined}
      className={cn(controlBase, "resize-y py-2.5 leading-relaxed", className)}
      {...props}
    />
  );
});

export const Select = React.forwardRef<
  HTMLSelectElement,
  React.SelectHTMLAttributes<HTMLSelectElement> & { invalid?: boolean }
>(function Select({ className, invalid, children, ...props }, ref) {
  return (
    <div className="relative">
      <select
        ref={ref}
        aria-invalid={invalid || undefined}
        className={cn(
          controlBase,
          "h-10 cursor-pointer appearance-none pr-9",
          className,
        )}
        {...props}
      >
        {children}
      </select>
      <svg
        aria-hidden
        viewBox="0 0 20 20"
        className="pointer-events-none absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-faint"
      >
        <path
          d="M6 8l4 4 4-4"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.6"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
    </div>
  );
});

export function Checkbox({
  className,
  ...props
}: React.InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      type="checkbox"
      className={cn(
        "h-4 w-4 shrink-0 cursor-pointer rounded-[4px] border-line-strong text-brand accent-[#2f6b4f]",
        "focus-visible:shadow-focus",
        className,
      )}
      {...props}
    />
  );
}

/** Accessible radio rendered as a card — used for paper/feedback choices. */
export function RadioCard({
  checked,
  disabled,
  className,
  children,
  ...props
}: React.InputHTMLAttributes<HTMLInputElement>) {
  return (
    <label
      className={cn(
        "group flex cursor-pointer items-start gap-3 rounded-control border px-4 py-3 transition-colors duration-200",
        checked
          ? "border-brand bg-brand-tint"
          : "border-line bg-surface hover:border-line-strong hover:bg-surface-muted",
        disabled && "cursor-not-allowed opacity-55",
        className,
      )}
    >
      <input
        type="radio"
        checked={checked}
        disabled={disabled}
        className="mt-0.5 h-4 w-4 shrink-0 accent-[#2f6b4f]"
        {...props}
      />
      <span className="min-w-0 flex-1 text-body text-ink">{children}</span>
    </label>
  );
}
