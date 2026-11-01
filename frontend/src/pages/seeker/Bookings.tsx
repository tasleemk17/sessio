import { useQuery } from "@tanstack/react-query";
import { BookOpen, CalendarClock, Download, MessageSquareText, Package, Presentation, Video, type LucideIcon } from "lucide-react";
import { useState, type ReactNode } from "react";
import { Link, Navigate, useParams } from "react-router-dom";
import { api, download } from "../../api";
import { Avatar } from "../../components/Brand";
import Modal from "../../components/Modal";
import { useToast } from "../../components/Toast";
import { KIND_LABEL, dateOnly, dateTime, fileSize, rupees } from "../../format";
import type { Booking } from "../../types";

interface TypeConfig {
  label: string;
  icon: LucideIcon;
  subs: { key: string; label: string; tab: string }[];
  empty: string;
  hint: string;
  cta: string;
}

/** The five kinds of purchase, in the order they appear as pills at the top. */
const TYPES: Record<string, TypeConfig> = {
  calls: {
    label: "1:1 calls", icon: Video, empty: "Start searching for experts to book their time for insightful 1:1 sessions", hint: "Book a call", cta: "Search for experts",
    subs: [{ key: "upcoming", label: "Upcoming", tab: "upcoming" }, { key: "completed", label: "Completed", tab: "past" }],
  },
  dm: {
    label: "Priority DM", icon: MessageSquareText, empty: "Ask an expert one question and the written answer shows up here", hint: "Send a DM to an expert", cta: "Find an expert",
    subs: [{ key: "all", label: "", tab: "messages" }],
  },
  products: {
    label: "Products/Courses", icon: BookOpen, empty: "Guides and templates you buy are kept here for good", hint: "Browse products", cta: "Find experts",
    subs: [{ key: "all", label: "", tab: "documents" }],
  },
  webinars: {
    label: "Webinars & Cohorts", icon: Presentation, empty: "Join a webinar to get quick insights on your favourite topics", hint: "Book a webinar", cta: "Find experts",
    subs: [{ key: "upcoming", label: "Upcoming", tab: "webinar-upcoming" }, { key: "completed", label: "Completed", tab: "webinar-past" }],
  },
  packages: {
    label: "Packages", icon: Package, empty: "Packages are the best way to get consistent learning and support from an expert", hint: "Book a package", cta: "Find experts",
    subs: [{ key: "active", label: "Active", tab: "package-active" }, { key: "past", label: "Past", tab: "package-past" }],
  },
};

function Details({ b, onClose }: { b: Booking; onClose: () => void }) {
  const rows: [string, string][] = [
    ["Reference", b.reference],
    ["Type", KIND_LABEL[b.kind]],
    ["Expert", b.expert_name],
    ["Paid on", b.paid_at ? dateTime(b.paid_at) : "-"],
    ["Amount", b.via_package ? "Paid with a package credit" : rupees(b.amount_paise)],
    ["Status", b.status === "paid" ? "Confirmed" : b.status],
  ];
  if (b.kind === "call" && b.slot_start) rows.push(["Time", dateTime(b.slot_start)]);
  if (b.kind === "package") rows.push(["Valid until", b.valid_until ? dateOnly(b.valid_until) : "-"], ["Credits used", `${b.package_used ?? 0} of ${b.package_total ?? 0}`]);
  return (
    <Modal title="Booking details" onClose={onClose}>
      <p className="mb-4 font-semibold text-slate-100">{b.service_title}</p>
      <dl className="divide-y divide-ink-700 text-sm">
        {rows.map(([k, v]) => (
          <div key={k} className="flex justify-between gap-4 py-2.5">
            <dt className="text-slate-400">{k}</dt>
            <dd className="text-right font-medium text-slate-200">{v}</dd>
          </div>
        ))}
      </dl>
      {b.sessions.length > 0 && (
        <div className="mt-4">
          <p className="label">Dates</p>
          <ul className="space-y-1 text-sm text-slate-300">{b.sessions.map((s) => <li key={s}>{dateTime(s)}</li>)}</ul>
        </div>
      )}
      <Link to={`/e/${b.expert_handle}`} onClick={onClose} className="btn mt-5 w-full">View {b.expert_name}'s page</Link>
    </Modal>
  );
}

function Card({ b }: { b: Booking }) {
  const toast = useToast();
  const [open, setOpen] = useState(false);
  const live = b.slot_end ? new Date(b.slot_end) >= new Date() : false;

  let action: ReactNode = null;
  if ((b.kind === "call" || b.kind === "webinar") && b.meeting_link && live) {
    action = <a className="btn btn-primary" href={b.meeting_link} target="_blank" rel="noopener noreferrer"><Video size={15} /> Join {b.kind === "webinar" ? "webinar" : "call"}</a>;
  } else if (b.kind === "document" && b.has_file && b.file_name) {
    action = <button className="btn btn-primary" onClick={() => download(`/me/bookings/${b.id}/download`, b.file_name!).catch((e: Error) => toast(e.message, "error"))}><Download size={15} /> Access</button>;
  } else if (b.kind === "package") {
    action = <Link className="btn btn-primary" to={`/e/${b.expert_handle}`}>Book a session</Link>;
  }

  return (
    <article className="card overflow-hidden">
      <div className="border-b border-ink-700 px-5 py-3"><span className="chip">{KIND_LABEL[b.kind]}</span></div>
      <div className="p-5">
        <h3 className="text-lg font-semibold text-slate-100">{b.service_title}</h3>
        <Link to={`/e/${b.expert_handle}`} className="mt-1 inline-flex items-center gap-2 text-sm text-slate-400 underline-offset-2 hover:text-accent hover:underline">
          <Avatar name={b.expert_name} size={22} /> {b.expert_name}
        </Link>

        {(b.kind === "call" || b.kind === "webinar") && b.slot_start && (
          <p className="mt-4 flex w-fit items-center gap-2 rounded-lg bg-ink-800 px-3 py-2 text-sm text-slate-200">
            <CalendarClock size={15} className="text-accent" />
            {b.sessions.length > 1 ? `${b.sessions.length} sessions, starting ${dateTime(b.slot_start)}` : dateTime(b.slot_start)}
          </p>
        )}
        {b.kind === "document" && b.file_name && <p className="mt-3 text-sm text-slate-400">{b.file_name} ({fileSize(b.file_size ?? 0)})</p>}
        {b.kind === "dm" && (
          <div className="mt-4 space-y-3 text-sm">
            <p className="rounded-xl bg-ink-800 p-3 text-slate-300"><span className="label !mb-1">Your question</span>{b.note}</p>
            {b.answer ? <p className="rounded-xl border border-accent/30 bg-accent/5 p-3 text-slate-200"><span className="label !mb-1">Reply</span><span className="whitespace-pre-line">{b.answer}</span></p> : <p className="text-slate-500">Waiting for {b.expert_name} to reply.</p>}
          </div>
        )}
        {b.kind === "package" && (
          <div className="mt-4">
            <div className="flex justify-between text-sm text-slate-300">
              <span>{(b.package_total ?? 0) - (b.package_used ?? 0)} of {b.package_total} calls left</span>
              <span className="text-slate-500">until {b.valid_until ? dateOnly(b.valid_until) : "-"}</span>
            </div>
            <div className="mt-2 h-2 overflow-hidden rounded-full bg-ink-700" role="progressbar" aria-valuenow={b.package_used ?? 0} aria-valuemax={b.package_total ?? 0} aria-label="Credits used">
              <div className="h-full rounded-full bg-accent" style={{ width: `${((b.package_used ?? 0) / Math.max(1, b.package_total ?? 1)) * 100}%` }} />
            </div>
          </div>
        )}

        <div className="mt-5 flex flex-wrap justify-end gap-2">
          <button className="btn" onClick={() => setOpen(true)}>Booking Details</button>
          {action}
        </div>
      </div>
      {open && <Details b={b} onClose={() => setOpen(false)} />}
    </article>
  );
}

export default function Bookings() {
  const { type = "calls", sub } = useParams();
  const config = TYPES[type];
  const current = config?.subs.find((s) => s.key === sub) ?? config?.subs[0];
  const list = useQuery({ queryKey: ["bookings", current?.tab], queryFn: () => api<Booking[]>(`/me/bookings?tab=${current!.tab}`), enabled: !!current });
  if (!config || !current) return <Navigate to="/dashboard/bookings/calls" replace />;

  const Icon = config.icon;
  return (
    <div>
      <h1 className="text-3xl font-extrabold tracking-tight">Bookings</h1>
      <nav className="mt-5 flex flex-wrap gap-2" aria-label="Kind of booking">
        {Object.entries(TYPES).map(([key, t]) => (
          <Link key={key} to={`/dashboard/bookings/${key}`} aria-current={key === type ? "page" : undefined}
            className={`rounded-full border px-4 py-2 text-sm transition ${key === type ? "border-2 border-slate-100 font-semibold text-slate-100" : "border-ink-600 text-slate-400 hover:border-accent/60 hover:text-slate-100"}`}>
            {t.label}
          </Link>
        ))}
      </nav>

      {config.subs.length > 1 && (
        <div className="mt-5 flex gap-6 border-b border-ink-700">
          {config.subs.map((s) => (
            <Link key={s.key} to={`/dashboard/bookings/${type}/${s.key}`} aria-current={s.key === current.key ? "page" : undefined}
              className={`-mb-px border-b-2 pb-3 text-sm font-semibold transition ${s.key === current.key ? "border-slate-100 text-slate-100" : "border-transparent text-slate-400 hover:text-slate-100"}`}>
              {s.label}
            </Link>
          ))}
        </div>
      )}

      <div className="mt-6 space-y-4">
        {list.isLoading && <div className="skeleton h-40" />}
        {list.error && <p className="text-bad">{(list.error as Error).message}</p>}
        {list.isSuccess && list.data.length === 0 && (
          <div className="py-12 text-center">
            <p className="text-3xl font-extrabold text-slate-100">So empty..</p>
            <p className="mx-auto mt-2 max-w-md text-slate-400">{config.empty}</p>
            <div className="card mx-auto mt-8 flex max-w-xl items-center gap-4 p-4 text-left">
              <span className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl bg-accent/10 text-accent"><Icon size={24} /></span>
              <div className="flex-1"><p className="font-semibold text-slate-100">{config.hint}</p><p className="text-sm text-slate-400">Search for experts on Sessio</p></div>
              <Link to="/dashboard/find" className="btn btn-primary">Try Here</Link>
            </div>
          </div>
        )}
        {list.data?.map((b) => <Card key={b.id} b={b} />)}
      </div>
    </div>
  );
}
