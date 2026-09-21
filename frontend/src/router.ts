// a router for three routes does not need a routing library: history API plus a
// subscription to popstate, with query parameters carrying the split view's state

import { useCallback, useEffect, useState } from "react";

export interface Location {
  path: string;
  params: URLSearchParams;
}

function current(): Location {
  return { path: window.location.pathname, params: new URLSearchParams(window.location.search) };
}

export function useLocation(): Location {
  const [location, setLocation] = useState<Location>(current);

  useEffect(() => {
    const update = () => setLocation(current());
    window.addEventListener("popstate", update);
    window.addEventListener("squeegee:navigate", update);
    return () => {
      window.removeEventListener("popstate", update);
      window.removeEventListener("squeegee:navigate", update);
    };
  }, []);

  return location;
}

export function navigate(path: string, params?: URLSearchParams): void {
  const query = params?.toString();
  window.history.pushState({}, "", query ? `${path}?${query}` : path);
  window.dispatchEvent(new Event("squeegee:navigate"));
}

/** Update one query parameter, keeping the rest and the current path. */
export function useParamSetter(): (updates: Record<string, string | null>) => void {
  return useCallback((updates: Record<string, string | null>) => {
    const params = new URLSearchParams(window.location.search);
    for (const [key, value] of Object.entries(updates)) {
      if (value === null) params.delete(key);
      else params.set(key, value);
    }
    navigate(window.location.pathname, params);
  }, []);
}
