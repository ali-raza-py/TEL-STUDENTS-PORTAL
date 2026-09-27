"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { ApiError, apiFetch } from "@/lib/api-client";
import type { RequestOptions } from "@/lib/api-client";

/**
 * `useResource` is the one data-fetching primitive the whole app builds on.
 *
 * Every API-driven surface gets the same four states for free — idle, loading,
 * error and loaded — which is why pages never have to invent their own
 * "Something went wrong" markup. Errors are surfaced as `ApiError` so a view
 * can distinguish an expired session from a genuine failure.
 */

export type ResourceState<T> =
  | { status: "idle"; data: null; error: null }
  | { status: "loading"; data: T | null; error: null }
  | { status: "error"; data: null; error: ApiError }
  | { status: "success"; data: T; error: null };

export interface UseResourceOptions<T> {
  /** Skip fetching entirely (e.g. no session yet). */
  enabled?: boolean;
  /** Values that change the request; used as the cache key. */
  deps?: unknown[];
  /** Return the previous data while the next request is in flight. */
  keepPreviousData?: boolean;
  onSuccess?: (data: T) => void;
  onError?: (error: ApiError) => void;
}

export interface UseResourceResult<T> {
  state: ResourceState<T>;
  data: T | null;
  error: ApiError | null;
  isLoading: boolean;
  isError: boolean;
  isSuccess: boolean;
  refetch: () => void;
}

export function useResource<T>(
  fetcher: (signal: AbortSignal) => Promise<T>,
  options: UseResourceOptions<T> = {},
): UseResourceResult<T> {
  const { enabled = true, deps = [], keepPreviousData = false, onSuccess, onError } = options;

  const [state, setState] = useState<ResourceState<T>>({
    status: enabled ? "loading" : "idle",
    data: null,
    error: null,
  });
  const [nonce, setNonce] = useState(0);
  const fetcherRef = useRef(fetcher);
  fetcherRef.current = fetcher;
  const callbacks = useRef({ onSuccess, onError });
  callbacks.current = { onSuccess, onError };

  useEffect(() => {
    if (!enabled) {
      setState({ status: "idle", data: null, error: null });
      return;
    }
    const controller = new AbortController();
    let active = true;

    setState((previous) => {
      if (keepPreviousData && previous.data) {
        return { status: "loading", data: previous.data, error: null };
      }
      return { status: "loading", data: null, error: null };
    });

    fetcherRef
      .current(controller.signal)
      .then((data) => {
        if (!active) return;
        setState({ status: "success", data, error: null });
        callbacks.current.onSuccess?.(data);
      })
      .catch((cause: unknown) => {
        if (!active || (cause as Error)?.name === "AbortError") return;
        const error =
          cause instanceof ApiError
            ? cause
            : new ApiError(0, "unknown", "Something went wrong. Please try again.");
        setState({ status: "error", data: null, error });
        callbacks.current.onError?.(error);
      });

    return () => {
      active = false;
      controller.abort();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [enabled, nonce, ...deps]);

  const refetch = useCallback(() => setNonce((value) => value + 1), []);

  return {
    state,
    data: state.data,
    error: state.error,
    isLoading: state.status === "loading",
    isError: state.status === "error",
    isSuccess: state.status === "success",
    refetch,
  };
}

/** Convenience wrapper for GET endpoints that take a query object. */
export function useApi<T>(
  path: string,
  query?: RequestOptions["query"],
  options: UseResourceOptions<T> = {},
) {
  return useResource<T>(
    (signal) => apiFetch<T>(path, { signal, query }),
    { deps: [path, JSON.stringify(query ?? {})], ...options },
  );
}

/** Debounces a rapidly changing value (search boxes, filters). */
export function useDebounced<T>(value: T, delay = 320): T {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const timer = setTimeout(() => setDebounced(value), delay);
    return () => clearTimeout(timer);
  }, [value, delay]);
  return debounced;
}

/**
 * Mutation state: pending, error, and a `run` that never throws so callers
 * handle success inline and errors through `error`.
 */
export function useMutation<TArgs extends unknown[], TResult>(
  action: (...args: TArgs) => Promise<TResult>,
) {
  const [isPending, setIsPending] = useState(false);
  const [error, setError] = useState<ApiError | null>(null);
  const mounted = useRef(true);

  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  }, []);

  const run = useCallback(
    async (...args: TArgs): Promise<TResult | null> => {
      setIsPending(true);
      setError(null);
      try {
        const result = await action(...args);
        return result;
      } catch (cause) {
        const apiError =
          cause instanceof ApiError
            ? cause
            : new ApiError(0, "unknown", "Something went wrong. Please try again.");
        if (mounted.current) setError(apiError);
        return null;
      } finally {
        if (mounted.current) setIsPending(false);
      }
    },
    [action],
  );

  const reset = useCallback(() => setError(null), []);

  return { run, isPending, error, reset };
}

/** Tracks a client-side media query; used to switch the navigation pattern. */
export function useMediaQuery(query: string): boolean {
  const [matches, setMatches] = useState(false);
  useEffect(() => {
    const list = window.matchMedia(query);
    setMatches(list.matches);
    const handler = (event: MediaQueryListEvent) => setMatches(event.matches);
    list.addEventListener("change", handler);
    return () => list.removeEventListener("change", handler);
  }, [query]);
  return matches;
}
