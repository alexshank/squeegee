import { useCallback, useEffect, useRef, useState } from "react";
import { type RecordEvent, type Status, api } from "./api";

export interface Records {
  items: RecordEvent[];
  hasMore: boolean;
  loading: boolean;
  error: string | null;
  loadMore: () => void;
}

/**
 * The records of one stage, one page at a time.
 *
 * Pages accumulate as the developer asks for more, and start over whenever the
 * stage or either filter changes, because a cursor only means anything within
 * the query that produced it. Every request carries the generation it was made
 * in, so a page that arrives after the query changed is dropped rather than
 * appended to results it does not belong to.
 */
export function useRecords(
  runId: number,
  position: number,
  status: Status | null,
  search: string,
): Records {
  const [items, setItems] = useState<RecordEvent[]>([]);
  const [cursor, setCursor] = useState<string | null>(null);
  const [hasMore, setHasMore] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const generation = useRef(0);

  const load = useCallback(
    (from: string | null, requested: number) => {
      setLoading(true);
      setError(null);
      api
        .stageRecords(runId, position, {
          ...(status ? { status } : {}),
          ...(search ? { q: search } : {}),
          ...(from ? { cursor: from } : {}),
        })
        .then((page) => {
          if (requested !== generation.current) return;
          setItems((already) => (from === null ? page.items : [...already, ...page.items]));
          setCursor(page.next_cursor);
          setHasMore(page.has_more);
          setLoading(false);
        })
        .catch((failure: Error) => {
          if (requested !== generation.current) return;
          setError(failure.message);
          setLoading(false);
        });
    },
    [runId, position, status, search],
  );

  useEffect(() => {
    generation.current += 1;
    setItems([]);
    setCursor(null);
    setHasMore(false);
    load(null, generation.current);
    return () => {
      // anything still in flight belongs to a query that no longer applies
      generation.current += 1;
    };
  }, [load]);

  const loadMore = useCallback(() => {
    if (cursor !== null) load(cursor, generation.current);
  }, [cursor, load]);

  return { items, hasMore, loading, error, loadMore };
}
