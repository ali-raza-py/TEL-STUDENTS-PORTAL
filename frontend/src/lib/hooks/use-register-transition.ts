"use client";

import * as React from "react";

import { ApiError } from "@/lib/api-client";
import { useToast } from "@/components/ui/toast";

/**
 * One register mutation at a time, with a per-row busy flag.
 *
 * The register pages all need the same thing: call a state transition, show a
 * toast on success, surface the API's own message on failure, and refresh the
 * list. Doing that inline with `useMutation` invites a stale-result effect loop,
 * so the control flow lives here instead.
 */
export function useRegisterTransition<T>(options: {
  run: (args: { id: number; target: string; note: string }) => Promise<T>;
  onSuccess?: (result: T) => void;
  successTitle: string;
  describeSuccess?: (result: T) => string | undefined;
  onSettled?: () => void;
}) {  const { run, onSuccess, successTitle, describeSuccess, onSettled } = options;
  const toast = useToast();

  const [pendingKey, setPendingKey] = React.useState<string | null>(null);
  const [error, setError] = React.useState<ApiError | null>(null);

  const act = React.useCallback(
    async (id: number, target: string, note = ""): Promise<boolean> => {
      setError(null);
      setPendingKey(`${id}:${target}`);
      try {
        const result = await run({ id, target, note });
        toast.success(successTitle, describeSuccess?.(result));
        onSuccess?.(result);
        onSettled?.();
        return true;
      } catch (cause) {
        const apiError =
          cause instanceof ApiError
            ? cause
            : new ApiError(0, "unknown", "That change could not be saved. Please try again.");
        setError(apiError);
        toast.error("Change not saved", apiError.message);
        return false;
      } finally {
        setPendingKey(null);
      }
    },
    [run, onSuccess, describeSuccess, onSettled, successTitle, toast],
  );

  const isPendingFor = React.useCallback(
    (id: number, target: string) => pendingKey === `${id}:${target}`,
    [pendingKey],
  );

  return { act, pendingKey, isPendingFor, error, clearError: () => setError(null) };
}
