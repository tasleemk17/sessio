import { useQuery } from "@tanstack/react-query";
import { Gift } from "lucide-react";
import { api } from "../../api";
import { amount, dateOnly } from "../../format";
import type { Rewards as RewardsData } from "../../types";

export default function Rewards() {
  const rewards = useQuery({ queryKey: ["rewards"], queryFn: () => api<RewardsData>("/me/rewards") });
  const r = rewards.data;
  const progress = r && r.points_to_next !== null ? r.points / (r.points + r.points_to_next) : 1;
  return (
    <div>
      <h1 className="text-3xl font-extrabold tracking-tight">Rewards</h1>
      <p className="mt-1 text-slate-400">Earn 1 point for every ₹10 you spend. Points raise your level; redeeming them is coming soon.</p>
      {rewards.isLoading && <div className="skeleton mt-6 h-40" />}
      {rewards.error && <p className="mt-6 text-bad">{(rewards.error as Error).message}</p>}
      {r && (
        <>
          <div className="card mt-6 p-6">
            <div className="flex flex-wrap items-center justify-between gap-4">
              <div className="flex items-center gap-4">
                <span className="flex h-14 w-14 items-center justify-center rounded-2xl bg-accent/10 text-accent"><Gift size={28} /></span>
                <div>
                  <p className="text-4xl font-extrabold text-slate-100">{r.points}</p>
                  <p className="text-sm text-slate-400">points · {amount(r.spent_paise)} spent</p>
                </div>
              </div>
              <span className="chip text-sm">{r.tier}</span>
            </div>
            <div className="mt-5">
              <div className="h-2 overflow-hidden rounded-full bg-ink-700" role="progressbar" aria-valuenow={Math.round(progress * 100)} aria-valuemax={100} aria-label="Progress to the next level">
                <div className="h-full rounded-full bg-accent transition-all" style={{ width: `${Math.round(progress * 100)}%` }} />
              </div>
              <p className="mt-2 text-sm text-slate-400">{r.next_tier ? `${r.points_to_next} more points to reach ${r.next_tier}` : "You are at the highest level."}</p>
            </div>
          </div>

          <h2 className="mb-3 mt-8 font-semibold">Recent points</h2>
          {r.recent.length === 0 ? (
            <div className="card px-6 py-10 text-center text-slate-400">Nothing yet. Your first purchase earns points.</div>
          ) : (
            <ul className="card divide-y divide-ink-700">
              {r.recent.map((x, i) => (
                <li key={i} className="flex items-center justify-between gap-3 p-4 text-sm">
                  <div className="min-w-0"><p className="truncate font-medium text-slate-200">{x.title}</p><p className="text-xs text-slate-500">{dateOnly(x.at)}</p></div>
                  <span className="font-semibold text-accent">+{x.points}</span>
                </li>
              ))}
            </ul>
          )}
        </>
      )}
    </div>
  );
}
