"use client";

import * as React from "react";

/**
 * Page number that resets to 1 whenever the filters change.
 *
 * Resetting from an effect would fire a render that briefly shows page 3 of a
 * one-page result set. This adjusts the state during render instead — the
 * pattern React sanctions for "state derived from props changed" — so the very
 * first paint after a filter change is already correct.
 */
export function usePagedFilters<TFilters extends Record<string, unknown>>(filters: TFilters) {
  const key = JSON.stringify(filters);
  const [state, setState] = React.useState({ key, page: 1 });

  if (state.key !== key) {
    setState({ key, page: 1 });
  }

  const setPage = React.useCallback((page: number) => {
    setState((current) => (current.key === key ? { ...current, page } : current));
  }, [key]);

  return { page: state.page, setPage };
}
