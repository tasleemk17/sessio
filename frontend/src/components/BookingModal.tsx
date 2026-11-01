import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, Copy, Download, Loader2, Video } from "lucide-react";
import { useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { api, download, loadRazorpay, openRazorpay } from "../api";
import { useAuth } from "../auth";
import { dateOnly, dateTime, dayChip, fileSize, localDay, rupees, timeOnly } from "../format";
import type { Booking, BookingCreated, ExpertPublic, Service, Slots } from "../types";
import Modal from "./Modal";
import { useToast } from "./Toast";

type Stage = "choose" | "mock" | "paying" | "pending" | "done";
const MIN_QUESTION = 10;
const AFTER_PURCHASE: Record<string, string> = {
  call: "/dashboard/bookings/calls", document: "/dashboard/bookings/products", dm: "/dashboard/bookings/dm",
  webinar: "/dashboard/bookings/webinars", package: "/dashboard/bookings/packages",
};

export default function BookingModal({ expert, service, onClose }: { expert: ExpertPublic; service: Service; onClose: () => void }) {
  const { me, signedIn } = useAuth();
  const queryClient = useQueryClient();
  const toast = useToast();
  const [stage, setStage] = useState<Stage>("choose");
  const [day, setDay] = useState<string | null>(null);
  const [slot, setSlot] = useState<string | null>(null);
  const [note, setNote] = useState("");
  const [creditChoice, setCreditChoice] = useState<number | null | undefined>(undefined); // undefined = not chosen yet
  const [created, setCreated] = useState<BookingCreated | null>(null);
  const [result, setResult] = useState<Booking | null>(null);
  const [error, setError] = useState("");
  const paid = useRef(false); // Razorpay also reports "closed" after a successful payment; this tells the two apart

  const isCall = service.kind === "call";
  const slots = useQuery({
    queryKey: ["slots", expert.handle, service.id],
    queryFn: () => api<Slots>(`/experts/${expert.handle}/slots?service_id=${service.id}&days=7`),
    enabled: isCall,
  });

  // Packages the person already bought for this very call: a credit pays for the call
  const packages = useQuery({ queryKey: ["bookings", "package-active"], queryFn: () => api<Booking[]>("/me/bookings?tab=package-active"), enabled: isCall && signedIn });
  const usable = (packages.data ?? []).filter((p) => p.package_call_service_id === service.id);
  const creditId = creditChoice === undefined ? (usable[0]?.id ?? null) : creditChoice;
  const credit = usable.find((p) => p.id === creditId) ?? null;

  const shownSlots = useMemo(() => (slots.data?.slots ?? []).filter((iso) => !credit?.valid_until || new Date(iso) <= new Date(credit.valid_until)), [slots.data, credit]);
  const byDay = useMemo(() => {
    const groups = new Map<string, string[]>();
    for (const iso of shownSlots) groups.set(localDay(iso), [...(groups.get(localDay(iso)) ?? []), iso]);
    return groups;
  }, [shownSlots]);
  const days = [...byDay.keys()];
  const activeDay = day && byDay.has(day) ? day : days[0] ?? null;

  const finish = (booking: Booking) => {
    setResult(booking);
    setStage("done");
    for (const key of ["slots", "bookings", "home", "rewards", "experts"]) queryClient.invalidateQueries({ queryKey: [key] });
    queryClient.invalidateQueries({ queryKey: ["expert", expert.handle] });
  };

  const pay = useMutation({
    mutationFn: (body: { razorpay_payment_id?: string; razorpay_signature?: string }) => api<Booking>(`/bookings/${created!.booking.id}/pay`, { method: "POST", body }),
    onSuccess: (booking) => {
      paid.current = true;
      finish(booking);
    },
    onError: (e) => setError((e as Error).message),
  });

  async function openCheckout(c: BookingCreated) {
    const info = c.payment!;
    setStage("paying");
    setError("");
    try {
      await loadRazorpay();
      openRazorpay({
        key: info.key_id!,
        amount: info.amount_paise,
        currency: info.currency,
        order_id: info.order_id,
        name: "Sessio",
        description: service.title,
        prefill: { name: me?.name, email: me?.email },
        theme: { color: "#4f46e5" },
        handler: (r) => pay.mutate({ razorpay_payment_id: r.razorpay_payment_id, razorpay_signature: r.razorpay_signature }),
        modal: { ondismiss: () => !paid.current && setStage("pending") },
      });
    } catch (e) {
      setError((e as Error).message);
      setStage("pending");
    }
  }

  const create = useMutation({
    mutationFn: () => api<BookingCreated>("/bookings", {
      method: "POST",
      body: { service_id: service.id, slot_start: isCall ? slot : null, note, package_booking_id: isCall && credit ? credit.id : null },
    }),
    onSuccess: (c) => {
      setCreated(c);
      setError("");
      if (!c.payment) finish(c.booking); // free, or paid with a credit: confirmed straight away
      else if (c.payment.mode === "mock") setStage("mock");
      else void openCheckout(c);
    },
    onError: (e) => {
      setError((e as Error).message);
      queryClient.invalidateQueries({ queryKey: ["slots"] }); // the list may be out of date: someone else took the time
      queryClient.invalidateQueries({ queryKey: ["expert", expert.handle] });
      setSlot(null);
    },
  });

  const cancel = useMutation({
    mutationFn: () => api(`/bookings/${created!.booking.id}/cancel`, { method: "POST" }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["slots"] });
      onClose();
    },
  });

  const ready = isCall ? !!slot : service.kind === "dm" ? note.trim().length >= MIN_QUESTION : true;
  const price = rupees(service.price_paise);
  const buyLabel = credit ? "Book with 1 credit" : service.price_paise === 0 ? "Confirm (free)" : service.kind === "webinar" ? `Reserve a seat for ${price}` : `Continue to pay ${price}`;

  return (
    <Modal title={service.title} onClose={onClose}>
      {stage === "choose" && (
        <div className="space-y-5">
          <p className="text-sm text-slate-400">
            With <b className="text-slate-200">{expert.name}</b>
            {isCall && <> · {service.duration_min} minutes</>}
            {service.kind === "dm" && <> · reply within {service.reply_hours} hours</>}
            {service.kind === "document" && service.file_name && <> · {service.file_name} ({fileSize(service.file_size ?? 0)})</>}
            {service.kind === "webinar" && <> · {service.duration_min} minutes each · {service.spots_left} {service.spots_left === 1 ? "seat" : "seats"} left</>}
            {service.kind === "package" && <> · {service.credits} calls, valid {service.valid_days} days</>}
          </p>

          {service.kind === "webinar" && (
            <div>
              <p className="label">{service.sessions.length > 1 ? `${service.sessions.length} sessions (a cohort)` : "Date"}</p>
              <ul className="space-y-1.5 text-sm text-slate-200">{service.sessions.map((s) => <li key={s} className="rounded-lg bg-ink-800 px-3 py-2">{dateTime(s)}</li>)}</ul>
              <p className="mt-2 text-xs text-slate-500">Shown in your time zone. One video link works for every date.</p>
            </div>
          )}

          {service.kind === "package" && (
            <p className="rounded-lg bg-ink-800 p-3 text-sm text-slate-300">
              You get <b>{service.credits}</b> credits for <b>{service.call_service_title}</b>. Each one pays for a call, so you only choose a time when you are ready. After paying, open the call on {expert.name}'s page and book with a credit.
            </p>
          )}

          {isCall && usable.length > 0 && (
            <div className="rounded-xl border border-accent/30 bg-accent/5 p-3 text-sm">
              <p className="font-medium text-slate-100">You have a package for this call</p>
              <label className="mt-2 flex items-center gap-2 text-slate-300">
                <input type="radio" className="accent-indigo-600" checked={credit !== null} onChange={() => setCreditChoice(usable[0].id)} />
                Use a credit ({(usable[0].package_total ?? 0) - (usable[0].package_used ?? 0)} left, until {usable[0].valid_until ? dateOnly(usable[0].valid_until) : "-"})
              </label>
              <label className="mt-1 flex items-center gap-2 text-slate-300">
                <input type="radio" className="accent-indigo-600" checked={credit === null} onChange={() => { setCreditChoice(null); setSlot(null); }} />
                Pay {price} for this call instead
              </label>
            </div>
          )}

          {isCall && (
            <div>
              <p className="label">Pick a day and time</p>
              {slots.isLoading && <div className="skeleton h-24" />}
              {slots.isSuccess && days.length === 0 && <p className="rounded-lg border border-ink-700 p-4 text-sm text-slate-400">No free times in the next 7 days{credit ? " that your credit covers" : ""}. Please check back soon.</p>}
              {days.length > 0 && (
                <>
                  <div className="flex gap-2 overflow-x-auto pb-2" role="tablist" aria-label="Day">
                    {days.map((d) => {
                      const c = dayChip(d);
                      const on = d === activeDay;
                      return (
                        <button key={d} role="tab" aria-selected={on} onClick={() => { setDay(d); setSlot(null); }}
                          className={`shrink-0 rounded-xl border px-3.5 py-2 text-center text-sm transition ${on ? "border-accent bg-accent text-on-accent" : "border-ink-600 text-slate-300 hover:border-accent/60"}`}>
                          <span className="block text-xs opacity-80">{c.weekday}</span>
                          <span className="font-semibold">{c.date}</span>
                        </button>
                      );
                    })}
                  </div>
                  <div className="mt-3 grid grid-cols-3 gap-2 sm:grid-cols-4">
                    {(activeDay ? byDay.get(activeDay) ?? [] : []).map((iso) => (
                      <button key={iso} onClick={() => setSlot(iso)} aria-pressed={slot === iso}
                        className={`rounded-lg border px-2 py-2 text-sm font-medium transition ${slot === iso ? "border-accent bg-accent/10 text-accent ring-1 ring-accent" : "border-ink-600 text-slate-200 hover:border-accent/60"}`}>
                        {timeOnly(iso)}
                      </button>
                    ))}
                  </div>
                  <p className="mt-2 text-xs text-slate-500">Shown in your time zone ({Intl.DateTimeFormat().resolvedOptions().timeZone}).</p>
                </>
              )}
            </div>
          )}

          {(isCall || service.kind === "dm") && (
            <div>
              <label className="label" htmlFor="note">
                {service.kind === "dm" ? "Your question" : "What would you like to talk about? (optional)"}
              </label>
              <textarea id="note" className="input h-28" value={note} maxLength={2000} onChange={(e) => setNote(e.target.value)}
                placeholder={service.kind === "dm" ? "Be specific, so the answer can be too." : "A line or two helps the expert prepare."} />
              {service.kind === "dm" && note.trim().length < MIN_QUESTION && <p className="mt-1 text-xs text-slate-500">At least {MIN_QUESTION} characters.</p>}
            </div>
          )}

          {service.kind === "document" && <p className="rounded-lg bg-ink-800 p-3 text-sm text-slate-400">After you pay, the file appears under <b>Bookings &gt; Products/Courses</b> and you can download it any time.</p>}

          {error && <p role="alert" className="rounded-lg border border-rose-500/30 bg-rose-500/10 px-3 py-2 text-sm text-bad">{error}</p>}

          {signedIn ? (
            <button className="btn btn-primary w-full py-3" disabled={!ready || create.isPending || (service.kind === "webinar" && service.spots_left === 0)} onClick={() => create.mutate()}>
              {create.isPending && <Loader2 size={16} className="animate-spin" />}
              {service.kind === "webinar" && service.spots_left === 0 ? "Sold out" : buyLabel}
            </button>
          ) : (
            <Link to={`/login?next=${encodeURIComponent(`/e/${expert.handle}`)}`} className="btn btn-primary w-full py-3">
              Sign in to continue
            </Link>
          )}
        </div>
      )}

      {stage === "mock" && created?.payment && (
        <div className="space-y-4 text-center">
          <p className="text-4xl font-extrabold">{price}</p>
          <p className="text-sm text-slate-400">Demo payment. No real money moves. With Razorpay keys set on the server, this step opens the real Razorpay window (test mode).</p>
          {error && <p role="alert" className="text-sm text-bad">{error}</p>}
          <button className="btn btn-primary w-full py-3" disabled={pay.isPending} onClick={() => pay.mutate({})}>
            {pay.isPending && <Loader2 size={16} className="animate-spin" />} Pay {price} (demo)
          </button>
          <button className="text-sm text-slate-500 hover:text-slate-300" onClick={() => cancel.mutate()}>Cancel</button>
        </div>
      )}

      {stage === "paying" && (
        <p className="flex items-center justify-center gap-2 py-10 text-slate-400"><Loader2 className="animate-spin" size={18} /> Opening the payment window...</p>
      )}

      {stage === "pending" && created?.payment && (
        <div className="space-y-4 text-center">
          <p className="font-semibold text-slate-100">Payment not completed</p>
          <p className="text-sm text-slate-400">Your choice is held for a few minutes. You can try again or cancel it.</p>
          {error && <p role="alert" className="text-sm text-bad">{error}</p>}
          <div className="flex gap-2">
            <button className="btn flex-1" onClick={() => cancel.mutate()}>Cancel</button>
            <button className="btn btn-primary flex-1" onClick={() => void openCheckout(created)}>Try again</button>
          </div>
        </div>
      )}

      {stage === "done" && result && (
        <div className="space-y-4 text-center">
          <CheckCircle2 className="mx-auto text-ok" size={44} />
          {(result.kind === "call" || result.kind === "webinar") && result.slot_start && (
            <>
              <p className="text-xl font-bold">{result.kind === "webinar" ? "Your seat is reserved" : "You are booked"}</p>
              <p className="text-slate-300">{result.sessions.length > 1 ? `${result.sessions.length} sessions, starting ${dateTime(result.slot_start)}` : dateTime(result.slot_start)} with {result.expert_name}</p>
              {result.via_package && <p className="text-sm text-slate-400">Paid with a package credit.</p>}
              {result.meeting_link && (
                <div className="rounded-xl border border-ink-700 p-3 text-left">
                  <p className="label">Your video room</p>
                  <p className="break-all text-sm text-accent">{result.meeting_link}</p>
                  <div className="mt-3 flex gap-2">
                    <a className="btn btn-primary flex-1" href={result.meeting_link} target="_blank" rel="noopener noreferrer"><Video size={15} /> Open</a>
                    <button className="btn flex-1" onClick={() => navigator.clipboard.writeText(result.meeting_link!).then(() => toast("Link copied."))}><Copy size={15} /> Copy</button>
                  </div>
                </div>
              )}
            </>
          )}
          {result.kind === "package" && (
            <>
              <p className="text-xl font-bold">Package bought</p>
              <p className="text-sm text-slate-400">You have {result.package_total} credits until {result.valid_until ? dateOnly(result.valid_until) : "-"}. Open the call on {result.expert_name}'s page and choose "Use a credit".</p>
            </>
          )}
          {result.kind === "document" && (
            <>
              <p className="text-xl font-bold">It is yours</p>
              {result.file_name && (
                <button className="btn btn-primary w-full" onClick={() => download(`/me/bookings/${result.id}/download`, result.file_name!).catch((e: Error) => toast(e.message, "error"))}>
                  <Download size={15} /> Download {result.file_name}
                </button>
              )}
            </>
          )}
          {result.kind === "dm" && (
            <>
              <p className="text-xl font-bold">Question sent</p>
              <p className="text-sm text-slate-400">{result.expert_name} will reply within {service.reply_hours} hours. The answer shows up under Bookings &gt; Priority DM.</p>
            </>
          )}
          <div className="flex gap-2 pt-2">
            <button className="btn flex-1" onClick={onClose}>Close</button>
            <Link className="btn flex-1" to={AFTER_PURCHASE[result.kind] ?? "/dashboard"} onClick={onClose}>
              My bookings
            </Link>
          </div>
        </div>
      )}
    </Modal>
  );
}
