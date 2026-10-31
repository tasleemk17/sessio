import { useQuery } from "@tanstack/react-query";
import { Download, FileText, MessageSquareText, Video, Clock } from "lucide-react";
import { Link, Navigate, useParams } from "react-router-dom";
import { api, download } from "../api";
import { useAuth } from "../auth";
import { Avatar } from "../components/Brand";
import { useToast } from "../components/Toast";
import { dateTime, fileSize, rupees } from "../format";
import type { Booking } from "../types";

const TABS = [
  { key: "upcoming", label: "Upcoming calls", empty: "No calls coming up.", icon: Video },
  { key: "past", label: "Past calls", empty: "No past calls yet.", icon: Clock },
  { key: "documents", label: "Documents", empty: "You have not bought any documents yet.", icon: FileText },
  { key: "messages", label: "Messages", empty: "You have not asked any questions yet.", icon: MessageSquareText },
] as const;

function Who({ b }: { b: Booking }) {
  return (
    <Link to={`/e/${b.expert_handle}`} className="mt-1 inline-flex items-center gap-2 text-sm text-slate-400 hover:text-accent">
      <Avatar name={b.expert_name} size={22} /> {b.expert_name}
    </Link>
  );
}

function Row({ b }: { b: Booking }) {
  const toast = useToast();
  return (
    <article className="card p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <h3 className="font-semibold text-slate-100">{b.service_title}</h3>
          <Who b={b} />
        </div>
        <span className="text-sm font-medium text-slate-400">{rupees(b.amount_paise)}</span>
      </div>

      {b.kind === "call" && b.slot_start && (
        <div className="mt-4 flex flex-wrap items-center justify-between gap-3 rounded-xl bg-ink-800 p-3">
          <p className="text-sm text-slate-200">{dateTime(b.slot_start)}</p>
          {b.meeting_link && new Date(b.slot_end ?? 0) >= new Date() && (
            <a className="btn btn-primary" href={b.meeting_link} target="_blank" rel="noopener noreferrer">
              <Video size={15} /> Join call
            </a>
          )}
        </div>
      )}
      {b.kind === "call" && b.note && <p className="mt-3 text-sm text-slate-400">You wrote: {b.note}</p>}

      {b.kind === "document" && b.has_file && b.file_name && (
        <div className="mt-4 flex flex-wrap items-center justify-between gap-3 rounded-xl bg-ink-800 p-3">
          <p className="inline-flex items-center gap-2 text-sm text-slate-200">
            <FileText size={16} className="text-accent" /> {b.file_name} <span className="text-slate-500">({fileSize(b.file_size ?? 0)})</span>
          </p>
          <button className="btn btn-primary" onClick={() => download(`/me/bookings/${b.id}/download`, b.file_name!).catch((e: Error) => toast(e.message, "error"))}>
            <Download size={15} /> Download
          </button>
        </div>
      )}

      {b.kind === "dm" && (
        <div className="mt-4 space-y-3 text-sm">
          <p className="rounded-xl bg-ink-800 p-3 text-slate-300"><span className="label !mb-1">Your question</span>{b.note}</p>
          {b.answer ? (
            <p className="rounded-xl border border-accent/30 bg-accent/5 p-3 text-slate-200"><span className="label !mb-1">Reply</span><span className="whitespace-pre-line">{b.answer}</span></p>
          ) : (
            <p className="text-slate-500">Waiting for {b.expert_name} to reply.</p>
          )}
        </div>
      )}
    </article>
  );
}

export default function Dashboard() {
  const { tab = "upcoming" } = useParams();
  const { signedIn, loading } = useAuth();
  const current = TABS.find((t) => t.key === tab);
  const list = useQuery({ queryKey: ["bookings", tab], queryFn: () => api<Booking[]>(`/me/bookings?tab=${tab}`), enabled: signedIn && !!current });

  if (!signedIn) return <Navigate to="/login?next=/dashboard" replace />;
  if (!current) return <Navigate to="/dashboard" replace />;
  if (loading) return null;

  return (
    <div className="mx-auto max-w-3xl px-4 py-10">
      <h1 className="text-3xl font-extrabold tracking-tight">My bookings</h1>
      <nav className="mt-6 flex gap-1 overflow-x-auto border-b border-ink-700" aria-label="Booking type">
        {TABS.map(({ key, label, icon: Icon }) => (
          <Link key={key} to={`/dashboard/${key}`} aria-current={key === tab ? "page" : undefined}
            className={`-mb-px inline-flex shrink-0 items-center gap-2 border-b-2 px-4 py-3 text-sm font-medium transition ${key === tab ? "border-accent text-accent" : "border-transparent text-slate-400 hover:text-slate-100"}`}>
            <Icon size={16} /> {label}
          </Link>
        ))}
      </nav>

      <div className="mt-6 space-y-3">
        {list.isLoading && <div className="skeleton h-32" />}
        {list.error && <p className="text-bad">{(list.error as Error).message}</p>}
        {list.isSuccess && list.data.length === 0 && (
          <div className="card px-6 py-14 text-center">
            <p className="text-slate-300">{current.empty}</p>
            <Link to="/" className="btn btn-primary mt-4">Find an expert</Link>
          </div>
        )}
        {list.data?.map((b) => <Row key={b.id} b={b} />)}
      </div>
    </div>
  );
}
