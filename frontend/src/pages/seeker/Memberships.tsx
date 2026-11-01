import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Crown, Download, FileText } from "lucide-react";
import { Link } from "react-router-dom";
import { api, download } from "../../api";
import { useToast } from "../../components/Toast";
import { dateOnly, fileSize, rupees } from "../../format";
import type { Service, Subscription } from "../../types";

const STATE: Record<string, { label: string; tone: string }> = {
  active: { label: "Active", tone: "chip-ok" },
  cancelling: { label: "Ends after this month", tone: "chip-miss" },
  cancelled: { label: "Cancelled", tone: "chip-miss" },
  expired: { label: "Expired", tone: "chip-miss" },
};

function Documents({ sub }: { sub: Subscription }) {
  const toast = useToast();
  const docs = useQuery({ queryKey: ["member-docs", sub.id], queryFn: () => api<Service[]>(`/me/subscriptions/${sub.id}/documents`) });
  if (docs.isLoading) return <div className="skeleton mt-4 h-16" />;
  if (!docs.data?.length) return <p className="mt-4 text-sm text-slate-500">No documents yet. New ones appear here as {sub.expert_name} adds them.</p>;
  return (
    <ul className="mt-4 divide-y divide-ink-700 rounded-xl border border-ink-700">
      {docs.data.map((d) => (
        <li key={d.id} className="flex flex-wrap items-center justify-between gap-3 p-3">
          <span className="inline-flex items-center gap-2 text-sm text-slate-200"><FileText size={16} className="text-accent" /> {d.title}{d.file_size ? <span className="text-slate-500">({fileSize(d.file_size)})</span> : null}</span>
          <button className="btn" onClick={() => download(`/me/subscriptions/${sub.id}/documents/${d.id}/download`, d.file_name ?? "document").catch((e: Error) => toast(e.message, "error"))}><Download size={15} /> Access</button>
        </li>
      ))}
    </ul>
  );
}

function Row({ sub }: { sub: Subscription }) {
  const queryClient = useQueryClient();
  const toast = useToast();
  const state = STATE[sub.status] ?? STATE.expired;
  const cancel = useMutation({
    mutationFn: () => api<Subscription>(`/subscriptions/${sub.id}/cancel`, { method: "POST" }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["subs"] });
      toast("Renewal stopped. You keep access until the month ends.");
    },
    onError: (e) => toast((e as Error).message, "error"),
  });
  return (
    <article className="card p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <h3 className="flex flex-wrap items-center gap-2 text-lg font-semibold text-slate-100">{sub.service_title} <span className={`chip ${state.tone}`}>{state.label}</span></h3>
          <Link to={`/e/${sub.expert_handle}`} className="text-sm text-slate-400 underline-offset-2 hover:text-accent hover:underline">{sub.expert_name}</Link>
        </div>
        <p className="text-right text-sm text-slate-400"><b className="text-base text-slate-100">{rupees(sub.amount_paise)}</b> / month<br />{sub.payments} {sub.payments === 1 ? "month" : "months"} paid</p>
      </div>
      <p className="mt-3 text-sm text-slate-400">
        {sub.has_access ? `${sub.status === "active" ? "Paid up to" : "Access until"} ${sub.current_period_end ? dateOnly(sub.current_period_end) : "-"}` : `Ended on ${sub.current_period_end ? dateOnly(sub.current_period_end) : "-"}`}
        {` · ${sub.documents_included} ${sub.documents_included === 1 ? "document" : "documents"} included`}
      </p>
      {sub.has_access && <Documents sub={sub} />}
      <div className="mt-4 flex justify-end gap-2">
        {sub.status === "active" && <button className="btn" disabled={cancel.isPending} onClick={() => window.confirm("Stop the monthly renewal? You keep access until the month you paid for ends.") && cancel.mutate()}>Cancel renewal</button>}
        {!sub.has_access && <Link className="btn btn-primary" to={`/e/${sub.expert_handle}`}>Renew</Link>}
      </div>
    </article>
  );
}

export default function Memberships() {
  const subs = useQuery({ queryKey: ["subs"], queryFn: () => api<Subscription[]>("/me/subscriptions") });
  return (
    <div>
      <h1 className="text-3xl font-extrabold tracking-tight">Memberships</h1>
      <p className="mt-1 text-slate-400">Subscribe to an expert and get all their documents while you are a member.</p>
      <div className="mt-6 space-y-4">
        {subs.isLoading && <div className="skeleton h-40" />}
        {subs.error && <p className="text-bad">{(subs.error as Error).message}</p>}
        {subs.isSuccess && subs.data.length === 0 && (
          <div className="py-12 text-center">
            <p className="text-3xl font-extrabold text-slate-100">So empty..</p>
            <p className="mx-auto mt-2 max-w-md text-slate-400">Join a membership to get an expert's documents and updates every month.</p>
            <div className="card mx-auto mt-8 flex max-w-xl items-center gap-4 p-4 text-left">
              <span className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl bg-accent/10 text-accent"><Crown size={24} /></span>
              <div className="flex-1"><p className="font-semibold text-slate-100">Find a membership</p><p className="text-sm text-slate-400">Look for the Membership label on an expert's page</p></div>
              <Link to="/dashboard/find" className="btn btn-primary">Try Here</Link>
            </div>
          </div>
        )}
        {subs.data?.map((s) => <Row key={s.id} sub={s} />)}
      </div>
    </div>
  );
}
