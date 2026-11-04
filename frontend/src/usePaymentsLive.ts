import { useQuery } from "@tanstack/react-query";
import { API_BASE } from "./api";

type Health = { status: string; payments: string; live?: boolean };

/** Whether real money moves (the server has a LIVE Razorpay key). undefined while the server has not answered.
 *  The "test mode, no real money" notices are shown only when this is false, so a buyer who is really being
 *  charged is never told the payment is a demo. */
export function usePaymentsLive(): boolean | undefined {
  const { data } = useQuery({
    queryKey: ["health"],
    queryFn: async (): Promise<Health> => {
      const res = await fetch(`${API_BASE}/api/health`, { cache: "no-store" });
      if (!res.ok) throw new Error("health check failed");
      return res.json();
    },
    staleTime: 5 * 60_000,
    retry: 5,
  });
  return data?.live;
}
