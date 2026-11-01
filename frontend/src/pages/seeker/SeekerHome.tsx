import { useQuery } from "@tanstack/react-query";
import { CalendarCheck, Crown, FileText, MessageSquareText, Package, Presentation, Video, type LucideIcon } from "lucide-react";
import { Link } from "react-router-dom";
import { api } from "../../api";
import { dateTime } from "../../format";
import type { HomeSummary } from "../../types";

function Tile({ icon: Icon, label, value, to }: { icon: LucideIcon; label: string; value: number; to: string }) {
  return (
    <Link to={to} className="card p-4 transition hover:-translate-y-0.5 hover:border-accent/50">
      <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-accent/10 text-accent"><Icon size={18} /></span>
      <p className="mt-3 text-2xl font-bold text-slate-100">{value}</p>
      <p className="text-sm text-slate-400">{label}</p>
    </Link>
  );
}

export default function SeekerHome() {
  const home = useQuery({ queryKey: ["home"], queryFn: () => api<HomeSummary>("/me/home") });
  const h = home.data;
  const next = h?.next_session;
  const nextTime = next ? (next.sessions.find((s) => new Date(s) >= new Date()) ?? next.slot_start) : null;

  return (
    <div>
      <h1 className="text-3xl font-extrabold tracking-tight">{h ? `Hi ${h.name.split(" ")[0]}` : "Home"}</h1>
      <p className="mt-1 text-slate-400">Everything you booked, bought and asked, in one place.</p>

      {home.isLoading && <div className="skeleton mt-6 h-32" />}
      {home.error && <p className="mt-6 text-bad">{(home.error as Error).message}</p>}
      {h && (
        <>
          <div className="card mt-6 p-5">
            <p className="label">Next up</p>
            {next && nextTime ? (
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <p className="font-semibold text-slate-100">{next.service_title}</p>
                  <p className="text-sm text-slate-400">with {next.expert_name} · {dateTime(nextTime)}</p>
                </div>
                {next.meeting_link && <a className="btn btn-primary" href={next.meeting_link} target="_blank" rel="noopener noreferrer"><Video size={15} /> Open video room</a>}
              </div>
            ) : (
              <div className="flex flex-wrap items-center justify-between gap-3">
                <p className="text-slate-400">Nothing scheduled yet.</p>
                <Link to="/dashboard/find" className="btn btn-primary">Find an expert</Link>
              </div>
            )}
          </div>

          <div className="mt-4 grid grid-cols-2 gap-3 lg:grid-cols-3">
            <Tile icon={Video} label="Upcoming calls" value={h.upcoming_calls} to="/dashboard/bookings/calls" />
            <Tile icon={Presentation} label="Upcoming webinars" value={h.upcoming_webinars} to="/dashboard/bookings/webinars" />
            <Tile icon={FileText} label="Documents you own" value={h.documents} to="/dashboard/bookings/products" />
            <Tile icon={MessageSquareText} label="Answers pending" value={h.pending_replies} to="/dashboard/bookings/dm" />
            <Tile icon={Crown} label="Active memberships" value={h.active_memberships} to="/dashboard/memberships" />
            <Tile icon={Package} label="Active packages" value={h.active_packages} to="/dashboard/bookings/packages" />
          </div>
          <Link to="/dashboard/bookings" className="mt-6 inline-flex items-center gap-2 text-sm font-medium text-accent hover:underline"><CalendarCheck size={16} /> See all bookings</Link>
        </>
      )}
    </div>
  );
}
