"use client";

import * as ToastPrimitive from "@radix-ui/react-toast";
import { AlertCircle, CheckCircle2, Info, X } from "lucide-react";
import * as React from "react";

import { cn } from "@/lib/utils";

/**
 * Toasts. Success messages are only ever raised after the corresponding API
 * call resolves — there is no optimistic "submitted!" anywhere in the portal.
 */

type ToastTone = "success" | "error" | "info";

interface ToastItem {
  id: number;
  title: string;
  description?: string;
  tone: ToastTone;
}

interface ToastContextValue {
  toast: (input: { title: string; description?: string; tone?: ToastTone }) => void;
  success: (title: string, description?: string) => void;
  error: (title: string, description?: string) => void;
  info: (title: string, description?: string) => void;
}

const ToastContext = React.createContext<ToastContextValue | null>(null);

export function useToast(): ToastContextValue {
  const context = React.useContext(ToastContext);
  if (!context) throw new Error("useToast must be used inside <ToastProvider>");
  return context;
}

const toneStyles: Record<ToastTone, { icon: React.ReactNode; ring: string }> = {
  success: { icon: <CheckCircle2 className="h-4 w-4 text-success" aria-hidden />, ring: "border-success-soft" },
  error: { icon: <AlertCircle className="h-4 w-4 text-danger" aria-hidden />, ring: "border-danger-soft" },
  info: { icon: <Info className="h-4 w-4 text-info" aria-hidden />, ring: "border-info-soft" },
};

let counter = 0;

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [items, setItems] = React.useState<ToastItem[]>([]);

  const remove = React.useCallback((id: number) => {
    setItems((current) => current.filter((item) => item.id !== id));
  }, []);

  const push = React.useCallback(
    (input: { title: string; description?: string; tone?: ToastTone }) => {
      counter += 1;
      const item: ToastItem = {
        id: counter,
        title: input.title,
        description: input.description,
        tone: input.tone ?? "info",
      };
      setItems((current) => [...current.slice(-3), item]);
    },
    [],
  );

  const value = React.useMemo<ToastContextValue>(
    () => ({
      toast: push,
      success: (title, description) => push({ title, description, tone: "success" }),
      error: (title, description) => push({ title, description, tone: "error" }),
      info: (title, description) => push({ title, description, tone: "info" }),
    }),
    [push],
  );

  return (
    <ToastContext.Provider value={value}>
      <ToastPrimitive.Provider swipeDirection="right" duration={5200}>
        {children}
        {items.map((item) => (
          <ToastPrimitive.Root
            key={item.id}
            onOpenChange={(open) => !open && remove(item.id)}
            className={cn(
              "animate-slide-in flex items-start gap-3 rounded-card border bg-surface p-4 shadow-overlay",
              toneStyles[item.tone].ring,
            )}
          >
            <span className="mt-0.5 shrink-0">{toneStyles[item.tone].icon}</span>
            <div className="min-w-0 flex-1">
              <ToastPrimitive.Title className="text-body font-medium text-ink">
                {item.title}
              </ToastPrimitive.Title>
              {item.description ? (
                <ToastPrimitive.Description className="mt-0.5 text-small text-ink-muted">
                  {item.description}
                </ToastPrimitive.Description>
              ) : null}
            </div>
            <ToastPrimitive.Close
              aria-label="Dismiss notification"
              className="shrink-0 rounded p-1 text-ink-faint transition-colors hover:bg-surface-muted hover:text-ink"
            >
              <X className="h-3.5 w-3.5" aria-hidden />
            </ToastPrimitive.Close>
          </ToastPrimitive.Root>
        ))}
        <ToastPrimitive.Viewport className="fixed bottom-4 right-4 z-[60] flex w-[min(24rem,calc(100vw-2rem))] flex-col gap-2 outline-none max-sm:left-4 max-sm:right-4" />
      </ToastPrimitive.Provider>
    </ToastContext.Provider>
  );
}
