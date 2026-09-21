import { useEffect, useState } from "react";

export interface Loaded<Result> {
  data: Result | null;
  error: string | null;
  loading: boolean;
}

/** Load once per change of `dependencies`, keeping the last good value visible. */
export function useApi<Result>(
  load: () => Promise<Result>,
  dependencies: unknown[],
): Loaded<Result> {
  const [state, setState] = useState<Loaded<Result>>({
    data: null,
    error: null,
    loading: true,
  });

  // biome-ignore lint/correctness/useExhaustiveDependencies: the caller decides what identifies its request
  useEffect(() => {
    let current = true;
    setState((previous) => ({ ...previous, loading: true, error: null }));
    load()
      .then((data) => current && setState({ data, error: null, loading: false }))
      .catch(
        (error: Error) => current && setState({ data: null, error: error.message, loading: false }),
      );
    return () => {
      current = false;
    };
  }, dependencies);

  return state;
}
