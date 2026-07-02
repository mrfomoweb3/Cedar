import { useCallback, useEffect, useRef, useState } from 'react';

/** Poll an async fetcher on an interval; returns latest data + loading/error. */
export function usePoll<T>(fetcher: () => Promise<T>, intervalMs = 3000) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const savedFetcher = useRef(fetcher);
  savedFetcher.current = fetcher;

  const tick = useCallback(async () => {
    try {
      const d = await savedFetcher.current();
      setData(d);
      setError(null);
    } catch (e) {
      setError((e as Error).message);
    }
  }, []);

  useEffect(() => {
    tick();
    const id = setInterval(tick, intervalMs);
    return () => clearInterval(id);
  }, [tick, intervalMs]);

  return { data, error, refresh: tick };
}
