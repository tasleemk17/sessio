import { useEffect, useState } from "react";
import { API_BASE } from "./api";

/** Pings the API the moment the page opens. Free hosting puts the server to sleep when it is idle, and the
 *  first answer can then take about a minute. This wakes it early, and `waking` turns true when the wait is
 *  long enough that the person should be told what is happening. It keeps trying until the server answers. */
export function useServerWake(slowAfterMs = 2500): { waking: boolean } {
  const [waking, setWaking] = useState(false);

  useEffect(() => {
    let alive = true;
    const timer = setTimeout(() => alive && setWaking(true), slowAfterMs);

    (async () => {
      for (let attempt = 0; attempt < 24 && alive; attempt++) {
        try {
          const res = await fetch(`${API_BASE}/api/health`, { cache: "no-store" });
          if (res.ok) break;
        } catch {
          /* still starting: the host answers with an error page until the server is up */
        }
        await new Promise((resolve) => setTimeout(resolve, 5000));
      }
      if (alive) {
        clearTimeout(timer);
        setWaking(false);
      }
    })();

    return () => {
      alive = false;
      clearTimeout(timer);
    };
  }, [slowAfterMs]);

  return { waking };
}
