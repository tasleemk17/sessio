import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { BarChart3, CalendarDays, Check, Copy, Eye, EyeOff, FileUp, Inbox, Loader2, Pencil, Plus, Trash2, UserRound } from "lucide-react";
import { useState, type FormEvent } from "react";
import { Link, Navigate, useParams } from "react-router-dom";
import { api, download } from "../api";
import { useAuth } from "../auth";
import Modal from "../components/Modal";
import { useToast } from "../components/Toast";
import { CATEGORY_LABEL, KIND_LABEL, WEEKDAYS, amount, dateTime, fileSize, fromClock, fromLocalInput, rupees, toClock, toLocalInput } from "../format";
import type { Booking, Category, ExpertMe, Kind, Service, Summary, Window } from "../types";
import { usePaymentsLive } from "../usePaymentsLive";

const TABS = [
  { key: "overview", label: "Overview", icon: BarChart3 },
  { key: "services", label: "Services", icon: Pencil },
  { key: "hours", label: "Hours", icon: CalendarDays },
  { key: "orders", label: "Orders", icon: Inbox },
  { key: "profile", label: "Profile", icon: UserRound },
] as const;

const zones = (): string[] => {
  const all = typeof Intl.supportedValuesOf === "function" ? Intl.supportedValuesOf("timeZone") : [];
  return all.length ? all : ["Asia/Kolkata", "UTC", "Europe/London", "America/New_York", "Asia/Dubai", "Asia/Singapore"];
};

// ------------------------------------------------------------------ first visit: create the page

function Onboarding() {
  const { refresh } = useAuth();
  const toast = useToast();
  const [handle, setHandle] = useState("");
  const [headline, setHeadline] = useState("");
  const [bio, setBio] = useState("");
  const [timezone, setTimezone] = useState(Intl.DateTimeFormat().resolvedOptions().timeZone || "Asia/Kolkata");
  const [category, setCategory] = useState<Category>("other");
  const create = useMutation({
    mutationFn: () => api("/expert", { method: "POST", body: { handle, headline, bio, timezone, category } }),
    onSuccess: () => {
      toast("Your page is live. Add your first service.");
      refresh();
    },
  });
  const submit = (e: FormEvent) => {
    e.preventDefault();
    create.mutate();
  };
  return (
    <div className="mx-auto max-w-xl px-4 py-10">
      <h1 className="text-3xl font-extrabold tracking-tight">Create your expert page</h1>
      <p className="mt-2 text-slate-400">One link people can open to book you. You can change everything later.</p>
      <form onSubmit={submit} className="card mt-6 space-y-4 p-5">
        <div>
          <label className="label" htmlFor="handle">Page name</label>
          <div className="flex items-center rounded-lg border border-ink-600 bg-ink-950/80 focus-within:border-accent focus-within:ring-2 focus-within:ring-accent/30">
            <span className="pl-3 text-sm text-slate-500">{location.host}/e/</span>
            <input id="handle" className="w-full bg-transparent px-1 py-2 text-sm text-slate-100 outline-none" value={handle} onChange={(e) => setHandle(e.target.value.toLowerCase())} required minLength={3} maxLength={30} placeholder="your-name" />
          </div>
          <p className="mt-1 text-xs text-slate-500">Letters, numbers and hyphens, 3 to 30 characters.</p>
        </div>
        <div>
          <label className="label" htmlFor="headline">Headline</label>
          <input id="headline" className="input" value={headline} maxLength={120} onChange={(e) => setHeadline(e.target.value)} placeholder="Cloud engineer, 5 years. I help freshers get their first AWS role." />
        </div>
        <div>
          <label className="label" htmlFor="bio">About you</label>
          <textarea id="bio" className="input h-28" value={bio} maxLength={2000} onChange={(e) => setBio(e.target.value)} />
        </div>
        <div>
          <label className="label" htmlFor="cat">What do you help with?</label>
          <select id="cat" className="input" value={category} onChange={(e) => setCategory(e.target.value as Category)}>
            {Object.entries(CATEGORY_LABEL).map(([key, label]) => <option key={key} value={key}>{label}</option>)}
          </select>
        </div>
        <div>
          <label className="label" htmlFor="tz">Your time zone</label>
          <select id="tz" className="input" value={timezone} onChange={(e) => setTimezone(e.target.value)}>
            {zones().map((z) => <option key={z}>{z}</option>)}
          </select>
        </div>
        {create.error && <p role="alert" className="text-sm text-bad">{(create.error as Error).message}</p>}
        <button className="btn btn-primary w-full py-3" disabled={create.isPending}>{create.isPending && <Loader2 size={16} className="animate-spin" />} Create my page</button>
      </form>
    </div>
  );
}

// ------------------------------------------------------------------ overview

function Stat({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div className="card p-4">
      <p className="text-xs font-medium uppercase tracking-wide text-slate-400">{label}</p>
      <p className="mt-1.5 text-2xl font-bold text-slate-100">{value}</p>
      {hint && <p className="mt-0.5 text-xs text-slate-500">{hint}</p>}
    </div>
  );
}

function Overview({ handle }: { handle: string }) {
  const toast = useToast();
  const live = usePaymentsLive();
  const summary = useQuery({ queryKey: ["summary"], queryFn: () => api<Summary>("/expert/summary") });
  const services = useQuery({ queryKey: ["my-services"], queryFn: () => api<Service[]>("/expert/services") });
  const hours = useQuery({ queryKey: ["hours"], queryFn: () => api<Window[]>("/expert/availability") });
  const link = `${location.origin}/e/${handle}`;
  const s = summary.data;
  const steps = [
    { done: (services.data?.length ?? 0) > 0, text: "Add a service", to: "/expert/services" },
    { done: (hours.data?.length ?? 0) > 0, text: "Set the hours you take calls", to: "/expert/hours" },
    { done: (s?.orders ?? 0) > 0, text: "Share your link and get your first order", to: "" },
  ];
  return (
    <div className="space-y-6">
      <div className="card flex flex-wrap items-center justify-between gap-3 p-4">
        <div className="min-w-0">
          <p className="label !mb-0.5">Your page</p>
          <Link to={`/e/${handle}`} className="break-all font-medium text-accent hover:underline">{link}</Link>
        </div>
        <button className="btn" onClick={() => navigator.clipboard.writeText(link).then(() => toast("Link copied."))}><Copy size={15} /> Copy link</button>
      </div>

      {s && (
        <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
          <Stat label="You earn" value={amount(s.net_paise)} hint={`after ${s.fee_percent}% platform fee`} />
          <Stat label="Sales" value={amount(s.gross_paise)} hint={`${s.orders} orders`} />
          <Stat label="Upcoming calls" value={String(s.upcoming_calls)} />
          <Stat label="Questions to answer" value={String(s.pending_dms)} />
        </div>
      )}

      <div className="card p-5">
        <h2 className="font-semibold">Getting started</h2>
        <ul className="mt-3 space-y-2">
          {steps.map((st) => (
            <li key={st.text} className="flex items-center gap-3 text-sm">
              <span className={`flex h-5 w-5 items-center justify-center rounded-full ${st.done ? "bg-accent text-on-accent" : "border border-ink-600"}`}>{st.done && <Check size={12} strokeWidth={3} />}</span>
              {st.to && !st.done ? <Link to={st.to} className="text-accent hover:underline">{st.text}</Link> : <span className={st.done ? "text-slate-500 line-through" : "text-slate-300"}>{st.text}</span>}
            </li>
          ))}
        </ul>
      </div>
      {live === false && <p className="text-xs text-slate-500">Earnings are for demonstration: payments run in test mode and nothing is paid out.</p>}
    </div>
  );
}

// ------------------------------------------------------------------ services

interface ServiceDraft {
  kind: Kind;
  title: string;
  description: string;
  price_rupees: number;
  duration_min: number;
  reply_hours: number;
  is_active: boolean;
  capacity: number;
  sessions: string[]; // as the datetime-local inputs hold them: the expert's own clock
  call_service_id: number | null;
  credits: number;
  valid_days: number;
}

const DEFAULT_PRICE: Record<Kind, number> = { call: 500, document: 199, dm: 99, webinar: 299, package: 1200, membership: 299 };
const TITLE_HINT: Record<Kind, string> = {
  call: "Resume review and career advice", document: "AWS Cloud Practitioner study plan", dm: "Ask me anything about AWS",
  webinar: "Cloud careers for freshers, live", package: "3 mock interviews", membership: "Monthly club: every guide I write",
};

function nextSession(daysAhead: number): string {
  const d = new Date(Date.now() + daysAhead * 86400000);
  d.setMinutes(0, 0, 0);
  d.setHours(19);
  return toLocalInput(d.toISOString());
}

function ServiceForm({ existing, onClose }: { existing: Service | null; onClose: () => void }) {
  const queryClient = useQueryClient();
  const mine = useQuery({ queryKey: ["my-services"], queryFn: () => api<Service[]>("/expert/services") });
  const calls = (mine.data ?? []).filter((s) => s.kind === "call");
  const [draft, setDraft] = useState<ServiceDraft>({
    kind: existing?.kind ?? "call",
    title: existing?.title ?? "",
    description: existing?.description ?? "",
    price_rupees: (existing?.price_paise ?? 50000) / 100,
    duration_min: existing?.duration_min ?? 30,
    reply_hours: existing?.reply_hours ?? 48,
    is_active: existing?.is_active ?? true,
    capacity: existing?.capacity ?? 30,
    sessions: existing?.sessions.length ? existing.sessions.map(toLocalInput) : [nextSession(3)],
    call_service_id: existing?.call_service_id ?? null,
    credits: existing?.credits ?? 3,
    valid_days: existing?.valid_days ?? 60,
  });
  const set = <K extends keyof ServiceDraft>(k: K, v: ServiceDraft[K]) => setDraft((d) => ({ ...d, [k]: v }));
  const pickKind = (kind: Kind) => setDraft((d) => ({ ...d, kind, price_rupees: DEFAULT_PRICE[kind], duration_min: kind === "webinar" ? 60 : 30 }));
  const kind = draft.kind;
  const save = useMutation({
    mutationFn: () => {
      const body = {
        kind, title: draft.title, description: draft.description, price_rupees: draft.price_rupees, is_active: draft.is_active,
        duration_min: kind === "call" || kind === "webinar" ? draft.duration_min : null,
        reply_hours: kind === "dm" ? draft.reply_hours : null,
        capacity: kind === "webinar" ? draft.capacity : null,
        sessions: kind === "webinar" ? draft.sessions.filter(Boolean).map(fromLocalInput) : [],
        call_service_id: kind === "package" ? (draft.call_service_id ?? calls[0]?.id ?? null) : null,
        credits: kind === "package" ? draft.credits : null,
        valid_days: kind === "package" ? draft.valid_days : null,
      };
      return existing ? api<Service>(`/expert/services/${existing.id}`, { method: "PUT", body }) : api<Service>("/expert/services", { method: "POST", body });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["my-services"] });
      onClose();
    },
  });
  const submit = (e: FormEvent) => {
    e.preventDefault();
    save.mutate();
  };
  const minPrice = kind === "membership" ? 10 : kind === "package" ? 1 : 0;
  return (
    <Modal title={existing ? "Edit service" : "Add a service"} onClose={onClose} wide>
      <form onSubmit={submit} className="space-y-4">
        <div>
          <label className="label" htmlFor="kind">Type</label>
          <select id="kind" className="input" value={kind} disabled={!!existing} onChange={(e) => pickKind(e.target.value as Kind)}>
            <option value="call">1:1 video call</option>
            <option value="dm">Priority DM (a written answer)</option>
            <option value="document">Document (a file people download)</option>
            <option value="webinar">Webinar or cohort (live, on set dates)</option>
            <option value="package">Package (several calls at one price)</option>
            <option value="membership">Membership (monthly subscription)</option>
          </select>
        </div>
        <div>
          <label className="label" htmlFor="title">Title</label>
          <input id="title" className="input" value={draft.title} onChange={(e) => set("title", e.target.value)} required minLength={3} maxLength={120} placeholder={TITLE_HINT[kind]} />
        </div>
        <div>
          <label className="label" htmlFor="desc">What do they get?</label>
          <textarea id="desc" className="input h-24" value={draft.description} onChange={(e) => set("description", e.target.value)} maxLength={2000} />
        </div>
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="label" htmlFor="price">{kind === "membership" ? "Price per month (₹)" : "Price (₹)"}</label>
            <input id="price" type="number" min={minPrice} max={50000} className="input" value={draft.price_rupees} onChange={(e) => set("price_rupees", Math.max(0, Math.floor(Number(e.target.value) || 0)))} />
            <p className="mt-1 text-xs text-slate-500">{minPrice === 0 ? "0 makes it free." : `At least ₹${minPrice}.`}</p>
          </div>
          {(kind === "call" || kind === "webinar") && (
            <div>
              <label className="label" htmlFor="dur">{kind === "webinar" ? "Length of each session" : "Length"}</label>
              <select id="dur" className="input" value={draft.duration_min} onChange={(e) => set("duration_min", Number(e.target.value))}>
                {(kind === "webinar" ? [30, 45, 60, 90, 120, 180] : [15, 30, 45, 60, 90]).map((m) => <option key={m} value={m}>{m} minutes</option>)}
              </select>
            </div>
          )}
          {kind === "dm" && (
            <div>
              <label className="label" htmlFor="reply">You reply within</label>
              <select id="reply" className="input" value={draft.reply_hours} onChange={(e) => set("reply_hours", Number(e.target.value))}>
                {[24, 48, 72, 168].map((h) => <option key={h} value={h}>{h} hours</option>)}
              </select>
            </div>
          )}
          {kind === "webinar" && (
            <div>
              <label className="label" htmlFor="seats">Seats</label>
              <input id="seats" type="number" min={1} max={500} className="input" value={draft.capacity} onChange={(e) => set("capacity", Math.min(500, Math.max(1, Math.floor(Number(e.target.value) || 1))))} />
            </div>
          )}
          {kind === "package" && (
            <>
              <div className="col-span-2">
                <label className="label" htmlFor="call">Which call is it a bundle of?</label>
                <select id="call" className="input" value={draft.call_service_id ?? calls[0]?.id ?? ""} onChange={(e) => set("call_service_id", Number(e.target.value))} disabled={!!existing}>
                  {calls.length === 0 && <option value="">Add a 1:1 call first</option>}
                  {calls.map((c) => <option key={c.id} value={c.id}>{c.title} ({rupees(c.price_paise)})</option>)}
                </select>
              </div>
              <div>
                <label className="label" htmlFor="credits">Number of calls</label>
                <input id="credits" type="number" min={2} max={20} className="input" value={draft.credits} onChange={(e) => set("credits", Math.min(20, Math.max(2, Math.floor(Number(e.target.value) || 2))))} />
              </div>
              <div>
                <label className="label" htmlFor="valid">Valid for (days)</label>
                <input id="valid" type="number" min={7} max={365} className="input" value={draft.valid_days} onChange={(e) => set("valid_days", Math.min(365, Math.max(7, Math.floor(Number(e.target.value) || 7))))} />
              </div>
            </>
          )}
        </div>

        {kind === "webinar" && (
          <div>
            <p className="label">Dates</p>
            <p className="mb-2 text-xs text-slate-500">One date makes a webinar. Several make a cohort: buyers get every date with one ticket. Times are in your own clock.</p>
            <div className="space-y-2">
              {draft.sessions.map((value, i) => (
                <div key={i} className="flex gap-2">
                  <input type="datetime-local" aria-label={`Session ${i + 1}`} className="input" value={value} onChange={(e) => set("sessions", draft.sessions.map((x, j) => (j === i ? e.target.value : x)))} required />
                  {draft.sessions.length > 1 && <button type="button" className="btn" aria-label="Remove date" onClick={() => set("sessions", draft.sessions.filter((_, j) => j !== i))}><Trash2 size={15} /></button>}
                </div>
              ))}
            </div>
            {draft.sessions.length < 12 && <button type="button" className="btn mt-2" onClick={() => set("sessions", [...draft.sessions, nextSession(3 + 7 * draft.sessions.length)])}><Plus size={15} /> Add a date</button>}
          </div>
        )}
        {kind === "membership" && <p className="rounded-lg bg-ink-800 p-3 text-sm text-slate-400">Members get every document you sell while they are subscribed, including ones you add later. Billing is monthly through Razorpay.</p>}

        <label className="flex items-center gap-2 text-sm text-slate-300">
          <input type="checkbox" className="accent-indigo-600" checked={draft.is_active} onChange={(e) => set("is_active", e.target.checked)} /> Visible on my page
        </label>
        {save.error && <p role="alert" className="text-sm text-bad">{(save.error as Error).message}</p>}
        <div className="flex justify-end gap-2">
          <button type="button" className="btn" onClick={onClose}>Cancel</button>
          <button className="btn btn-primary" disabled={save.isPending || (kind === "package" && calls.length === 0)}>{save.isPending && <Loader2 size={15} className="animate-spin" />} Save</button>
        </div>
      </form>
    </Modal>
  );
}

function FileForm({ service, onClose }: { service: Service; onClose: () => void }) {
  const queryClient = useQueryClient();
  const toast = useToast();
  const [file, setFile] = useState<File | null>(null);
  const [agree, setAgree] = useState(false);
  const upload = useMutation({
    mutationFn: () => {
      const form = new FormData();
      form.append("file", file!);
      form.append("declaration", "true");
      return api<Service>(`/expert/services/${service.id}/file`, { method: "POST", form });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["my-services"] });
      toast("File uploaded. People can buy it now.");
      onClose();
    },
  });
  return (
    <Modal title={service.file_name ? "Replace the file" : "Upload the file"} onClose={onClose}>
      <div className="space-y-4">
        <div>
          <label className="label" htmlFor="file">File (up to 5 MB)</label>
          <input id="file" type="file" className="input" accept=".pdf,.doc,.docx,.xls,.xlsx,.ppt,.pptx,.txt,.md,.png,.jpg,.jpeg,.zip" onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
          <p className="mt-1 text-xs text-slate-500">PDF, Word, Excel, PowerPoint, text, images or a zip.</p>
        </div>
        <label className="flex items-start gap-2 rounded-lg border border-ink-700 p-3 text-sm text-slate-300">
          <input type="checkbox" className="mt-1 accent-indigo-600" checked={agree} onChange={(e) => setAgree(e.target.checked)} />
          <span>I own this file or have the right to sell it, and it does <b>not</b> contain other people's personal contact details (phone numbers, personal emails) without their permission.</span>
        </label>
        {upload.error && <p role="alert" className="text-sm text-bad">{(upload.error as Error).message}</p>}
        <div className="flex justify-end gap-2">
          <button className="btn" onClick={onClose}>Cancel</button>
          <button className="btn btn-primary" disabled={!file || !agree || upload.isPending} onClick={() => upload.mutate()}>{upload.isPending && <Loader2 size={15} className="animate-spin" />} Upload</button>
        </div>
      </div>
    </Modal>
  );
}

function Services() {
  const queryClient = useQueryClient();
  const toast = useToast();
  const services = useQuery({ queryKey: ["my-services"], queryFn: () => api<Service[]>("/expert/services") });
  const [editing, setEditing] = useState<Service | "new" | null>(null);
  const [uploading, setUploading] = useState<Service | null>(null);
  const toggle = useMutation({
    mutationFn: (s: Service) => api(`/expert/services/${s.id}`, { method: "PUT", body: { kind: s.kind, title: s.title, description: s.description, price_rupees: s.price_paise / 100, duration_min: s.duration_min, reply_hours: s.reply_hours, is_active: !s.is_active } }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["my-services"] }),
  });
  const remove = useMutation({
    mutationFn: (s: Service) => api(`/expert/services/${s.id}`, { method: "DELETE" }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["my-services"] }),
    onError: (e) => toast((e as Error).message, "error"),
  });
  return (
    <div className="space-y-3">
      <div className="flex justify-end">
        <button className="btn btn-primary" onClick={() => setEditing("new")}><Plus size={16} /> Add a service</button>
      </div>
      {services.isSuccess && services.data.length === 0 && <div className="card px-6 py-12 text-center text-slate-400">No services yet. Add a call, a document or a priority DM.</div>}
      {services.data?.map((s) => (
        <article key={s.id} className={`card p-4 ${s.is_active ? "" : "opacity-60"}`}>
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div className="min-w-0">
              <p className="flex flex-wrap items-center gap-2 font-semibold text-slate-100">{s.title} <span className="chip">{KIND_LABEL[s.kind]}</span>{!s.is_active && <span className="chip chip-miss">Hidden</span>}</p>
              <p className="mt-1 text-sm text-slate-400">
                {rupees(s.price_paise)}{s.kind === "membership" ? " / month" : ""}{s.duration_min ? ` · ${s.duration_min} min` : ""}{s.reply_hours ? ` · reply in ${s.reply_hours}h` : ""}
                {s.kind === "webinar" ? ` · ${s.sessions.length} ${s.sessions.length === 1 ? "date" : "dates"}, ${s.spots_left} of ${s.capacity} seats left` : ""}
                {s.kind === "package" ? ` · ${s.credits} × ${s.call_service_title}, ${s.valid_days} days` : ""}
                {s.kind === "membership" ? ` · ${s.documents_included ?? 0} documents included` : ""}
              </p>
              {s.kind === "webinar" && s.sessions[0] && <p className="mt-1 text-xs text-slate-500">First: {dateTime(s.sessions[0])}</p>}
              {s.kind === "document" && (
                <p className="mt-2 text-sm">
                  {s.file_name ? <span className="text-slate-300">{s.file_name} ({fileSize(s.file_size ?? 0)}) · <button className="text-accent hover:underline" onClick={() => download(`/expert/services/${s.id}/file`, s.file_name!).catch((e: Error) => toast(e.message, "error"))}>download</button></span> : <span className="text-warn">No file yet. People cannot buy this until you upload one.</span>}
                </p>
              )}
            </div>
            <div className="flex flex-wrap gap-2">
              {s.kind === "document" && <button className="btn" onClick={() => setUploading(s)}><FileUp size={15} /> {s.file_name ? "Replace file" : "Upload file"}</button>}
              <button className="btn" onClick={() => setEditing(s)}><Pencil size={15} /> Edit</button>
              <button className="btn" onClick={() => toggle.mutate(s)} aria-label={s.is_active ? "Hide" : "Show"}>{s.is_active ? <EyeOff size={15} /> : <Eye size={15} />}</button>
              <button className="btn" onClick={() => window.confirm(`Delete "${s.title}"?`) && remove.mutate(s)} aria-label="Delete"><Trash2 size={15} /></button>
            </div>
          </div>
        </article>
      ))}
      {editing && <ServiceForm existing={editing === "new" ? null : editing} onClose={() => setEditing(null)} />}
      {uploading && <FileForm service={uploading} onClose={() => setUploading(null)} />}
    </div>
  );
}

// ------------------------------------------------------------------ weekly hours

function Hours({ timezone }: { timezone: string }) {
  const queryClient = useQueryClient();
  const toast = useToast();
  const saved = useQuery({ queryKey: ["hours"], queryFn: () => api<Window[]>("/expert/availability") });
  const [draft, setDraft] = useState<Window[] | null>(null);
  const windows = draft ?? saved.data ?? [];
  const change = (next: Window[]) => setDraft(next);
  const save = useMutation({
    mutationFn: () => api<Window[]>("/expert/availability", { method: "PUT", body: windows }),
    onSuccess: (data) => {
      queryClient.setQueryData(["hours"], data);
      setDraft(null);
      toast("Hours saved.");
    },
  });
  const bad = windows.some((w) => w.start_min >= w.end_min);
  return (
    <div className="space-y-4">
      <p className="text-sm text-slate-400">The times you take calls each week, in <b className="text-slate-200">{timezone}</b>. People see them in their own time zone.</p>
      <div className="card divide-y divide-ink-700">
        {WEEKDAYS.map((name, day) => {
          const mine = windows.map((w, i) => ({ w, i })).filter(({ w }) => w.weekday === day);
          return (
            <div key={name} className="flex flex-wrap items-center gap-3 p-4">
              <p className="w-28 text-sm font-medium text-slate-200">{name}</p>
              <div className="flex flex-1 flex-wrap items-center gap-2">
                {mine.length === 0 && <span className="text-sm text-slate-500">Unavailable</span>}
                {mine.map(({ w, i }) => (
                  <span key={i} className="inline-flex items-center gap-1.5 rounded-lg border border-ink-600 px-2 py-1">
                    <input type="time" aria-label={`${name} start`} className="bg-transparent text-sm text-slate-100 outline-none" value={toClock(w.start_min)} onChange={(e) => change(windows.map((x, j) => (j === i ? { ...x, start_min: fromClock(e.target.value) } : x)))} />
                    <span className="text-slate-500">to</span>
                    <input type="time" aria-label={`${name} end`} className="bg-transparent text-sm text-slate-100 outline-none" value={toClock(w.end_min)} onChange={(e) => change(windows.map((x, j) => (j === i ? { ...x, end_min: fromClock(e.target.value) } : x)))} />
                    <button className="text-slate-500 hover:text-bad" aria-label="Remove" onClick={() => change(windows.filter((_, j) => j !== i))}><Trash2 size={14} /></button>
                  </span>
                ))}
              </div>
              <button className="btn py-1.5" onClick={() => change([...windows, { weekday: day, start_min: 18 * 60, end_min: 21 * 60 }])}><Plus size={14} /> Add</button>
            </div>
          );
        })}
      </div>
      {bad && <p className="text-sm text-bad">Each window must end after it starts.</p>}
      {save.error && <p role="alert" className="text-sm text-bad">{(save.error as Error).message}</p>}
      <button className="btn btn-primary" disabled={!draft || bad || save.isPending} onClick={() => save.mutate()}>{save.isPending && <Loader2 size={15} className="animate-spin" />} Save hours</button>
    </div>
  );
}

// ------------------------------------------------------------------ orders

function Order({ b }: { b: Booking }) {
  const queryClient = useQueryClient();
  const [answer, setAnswer] = useState("");
  const send = useMutation({
    mutationFn: () => api<Booking>(`/expert/bookings/${b.id}/answer`, { method: "POST", body: { answer } }),
    onSuccess: () => {
      for (const key of ["orders", "summary"]) queryClient.invalidateQueries({ queryKey: [key] });
    },
  });
  return (
    <article className="card p-4">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <p className="font-semibold text-slate-100">{b.service_title} <span className="chip ml-1">{KIND_LABEL[b.kind]}</span></p>
          <p className="mt-1 text-sm text-slate-400">{b.seeker_name} · {b.paid_at ? dateTime(b.paid_at) : ""}</p>
        </div>
        <span className="font-semibold text-slate-200">{rupees(b.amount_paise)}</span>
      </div>
      {b.kind === "call" && b.slot_start && <p className="mt-3 rounded-lg bg-ink-800 p-2.5 text-sm text-slate-200">Call on {dateTime(b.slot_start)}{b.meeting_link && <> · <a href={b.meeting_link} target="_blank" rel="noopener noreferrer" className="text-accent hover:underline">video room</a></>}{b.note && <span className="mt-1 block text-slate-400">They wrote: {b.note}</span>}</p>}
      {b.kind === "webinar" && b.sessions.length > 0 && <p className="mt-3 rounded-lg bg-ink-800 p-2.5 text-sm text-slate-200">{b.sessions.length > 1 ? `${b.sessions.length} sessions: ` : ""}{b.sessions.map((x) => dateTime(x)).join(" · ")}</p>}
      {b.kind === "package" && <p className="mt-3 rounded-lg bg-ink-800 p-2.5 text-sm text-slate-200">{b.package_used ?? 0} of {b.package_total} calls used</p>}
      {b.kind === "dm" && (
        <div className="mt-3 space-y-2 text-sm">
          <p className="rounded-lg bg-ink-800 p-2.5 text-slate-300">{b.note}</p>
          {b.answer ? <p className="text-slate-400">Your reply: {b.answer}</p> : (
            <>
              <textarea className="input h-24" placeholder="Write your reply" value={answer} onChange={(e) => setAnswer(e.target.value)} maxLength={4000} />
              {send.error && <p role="alert" className="text-bad">{(send.error as Error).message}</p>}
              <button className="btn btn-primary" disabled={answer.trim().length < 5 || send.isPending} onClick={() => send.mutate()}>Send reply</button>
            </>
          )}
        </div>
      )}
    </article>
  );
}

function Orders() {
  const orders = useQuery({ queryKey: ["orders"], queryFn: () => api<Booking[]>("/expert/bookings") });
  return (
    <div className="space-y-3">
      {orders.isLoading && <div className="skeleton h-28" />}
      {orders.isSuccess && orders.data.length === 0 && <div className="card px-6 py-12 text-center text-slate-400">No orders yet. Share your page link to get the first one.</div>}
      {orders.data?.map((b) => <Order key={b.id} b={b} />)}
    </div>
  );
}

// ------------------------------------------------------------------ profile

function ProfileForm({ expert }: { expert: ExpertMe }) {
  const queryClient = useQueryClient();
  const toast = useToast();
  const [headline, setHeadline] = useState(expert.headline);
  const [bio, setBio] = useState(expert.bio);
  const [timezone, setTimezone] = useState(expert.timezone);
  const [category, setCategory] = useState<Category>(expert.category);
  const save = useMutation({
    mutationFn: () => api<ExpertMe>("/expert/me", { method: "PUT", body: { headline, bio, timezone, category } }),
    onSuccess: (data) => {
      queryClient.setQueryData(["expert-me"], data);
      toast("Profile saved.");
    },
  });
  return (
    <form onSubmit={(e) => { e.preventDefault(); save.mutate(); }} className="card space-y-4 p-5">
      <div>
        <label className="label" htmlFor="h">Headline</label>
        <input id="h" className="input" value={headline} maxLength={120} onChange={(e) => setHeadline(e.target.value)} />
      </div>
      <div>
        <label className="label" htmlFor="b">About you</label>
        <textarea id="b" className="input h-32" value={bio} maxLength={2000} onChange={(e) => setBio(e.target.value)} />
      </div>
      <div>
        <label className="label" htmlFor="c">Category</label>
        <select id="c" className="input" value={category} onChange={(e) => setCategory(e.target.value as Category)}>
          {Object.entries(CATEGORY_LABEL).map(([key, label]) => <option key={key} value={key}>{label}</option>)}
        </select>
      </div>
      <div>
        <label className="label" htmlFor="z">Time zone</label>
        <select id="z" className="input" value={timezone} onChange={(e) => setTimezone(e.target.value)}>
          {[...new Set([timezone, ...zones()])].map((z) => <option key={z}>{z}</option>)}
        </select>
      </div>
      {save.error && <p role="alert" className="text-sm text-bad">{(save.error as Error).message}</p>}
      <button className="btn btn-primary" disabled={save.isPending}>{save.isPending && <Loader2 size={15} className="animate-spin" />} Save profile</button>
    </form>
  );
}

// ------------------------------------------------------------------ the page

export default function ExpertStudio() {
  const { tab = "overview" } = useParams();
  const { me, signedIn, loading } = useAuth();
  const expert = useQuery({ queryKey: ["expert-me"], queryFn: () => api<ExpertMe>("/expert/me"), enabled: !!me?.handle });

  if (!signedIn) return <Navigate to="/login?next=/expert" replace />;
  if (loading || !me) return null;
  if (!me.handle) return me.can_be_expert ? <Onboarding /> : <Navigate to="/" replace />;
  if (!TABS.some((t) => t.key === tab)) return <Navigate to="/expert" replace />;

  return (
    <div className="mx-auto max-w-4xl px-4 py-10">
      <h1 className="text-3xl font-extrabold tracking-tight">Expert studio</h1>
      <nav className="mt-6 flex gap-1 overflow-x-auto border-b border-ink-700" aria-label="Studio sections">
        {TABS.map(({ key, label, icon: Icon }) => (
          <Link key={key} to={`/expert/${key}`} aria-current={key === tab ? "page" : undefined}
            className={`-mb-px inline-flex shrink-0 items-center gap-2 border-b-2 px-4 py-3 text-sm font-medium transition ${key === tab ? "border-accent text-accent" : "border-transparent text-slate-400 hover:text-slate-100"}`}>
            <Icon size={16} /> {label}
          </Link>
        ))}
      </nav>
      <div className="mt-6">
        {tab === "overview" && <Overview handle={me.handle} />}
        {tab === "services" && <Services />}
        {tab === "hours" && <Hours timezone={expert.data?.timezone ?? "Asia/Kolkata"} />}
        {tab === "orders" && <Orders />}
        {tab === "profile" && (expert.data ? <ProfileForm expert={expert.data} /> : <div className="skeleton h-48" />)}
      </div>
    </div>
  );
}
