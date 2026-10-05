import { useCallback, useEffect, useState } from "react";

export function useAsync(fn, deps = []) {
  const [state, set] = useState({ data: null, error: null, loading: true });
  const run = useCallback(() => {
    set((s) => ({ ...s, loading: true, error: null }));
    fn().then((data) => set({ data, error: null, loading: false }), (error) => set({ data: null, error: error.message, loading: false }));
  }, deps); // eslint-disable-line
  useEffect(run, [run]);
  return { ...state, reload: run };
}
