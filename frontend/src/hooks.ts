// Tiny async-data hook so every panel loads/refreshes uniformly.
import { useCallback, useEffect, useState } from "react";
import { loadSize, saveSize } from "./lib/layout";

/** Persisted, clamped pixel size for a resizable region (localStorage-backed). */
export function useResizable(key: string, initial: number, min: number, max: number) {
  const [size, setSize] = useState(() => loadSize(key, initial, min, max));
  useEffect(() => { saveSize(key, size); }, [key, size]);
  return [size, setSize] as const;
}

export function useAsync<T>(fn: () => Promise<T>, deps: unknown[]) {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const run = useCallback(() => {
    setLoading(true);
    setError(null);
    fn()
      .then((d) => setData(d))
      .catch((e) => setError(String(e?.message ?? e)))
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  useEffect(() => {
    run();
  }, [run]);

  return { data, loading, error, reload: run };
}
