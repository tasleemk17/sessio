import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api } from "../api";
import { CATEGORY_LABEL, rupees } from "../format";
import type { ExpertCard } from "../types";
import { Avatar } from "./Brand";

/** Expert cards for a search and/or a category, shared by the dashboard's Find People and Find by Category. */
export default function ExpertGrid({ q, category }: { q: string; category: string }) {
  const experts = useQuery({
    queryKey: ["experts", q, category],
    queryFn: () => api<ExpertCard[]>(`/experts?q=${encodeURIComponent(q)}&category=${encodeURIComponent(category)}`),
    placeholderData: (previous) => previous,
  });
  return (
    <div>
      {experts.isLoading && (
        <div className="grid gap-4 sm:grid-cols-2">
          {[0, 1].map((i) => <div key={i} className="skeleton h-36" />)}
        </div>
      )}
      {experts.error && <p className="text-bad">{(experts.error as Error).message}</p>}
      {experts.isSuccess && experts.data.length === 0 && (
        <div className="card px-6 py-12 text-center">
          <p className="font-semibold text-slate-200">No one matches that yet</p>
          <p className="mt-1 text-sm text-slate-400">Try a different word or category.</p>
        </div>
      )}
      <div className="grid gap-4 sm:grid-cols-2">
        {experts.data?.map((e) => (
          <Link key={e.handle} to={`/e/${e.handle}`} className="card p-5 transition hover:-translate-y-0.5 hover:border-accent/50 hover:shadow-lift">
            <div className="flex items-center gap-3">
              <Avatar name={e.name} />
              <div className="min-w-0">
                <p className="truncate font-semibold text-slate-100">{e.name}</p>
                <p className="truncate text-xs text-slate-500">{CATEGORY_LABEL[e.category] ?? e.category}</p>
              </div>
            </div>
            <p className="mt-3 line-clamp-2 min-h-10 text-sm text-slate-400">{e.headline || "No headline yet"}</p>
            <div className="mt-3 flex items-center justify-between text-sm">
              <span className="text-slate-500">{e.services} {e.services === 1 ? "service" : "services"}</span>
              {e.from_paise !== null && <span className="font-semibold text-accent">{e.from_paise === 0 ? "Free options" : `from ${rupees(e.from_paise)}`}</span>}
            </div>
          </Link>
        ))}
      </div>
    </div>
  );
}
