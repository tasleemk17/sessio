import { useMutation, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, Loader2 } from "lucide-react";
import { useRef, useState } from "react";
import { Link } from "react-router-dom";
import { api, loadRazorpay, openRazorpay } from "../api";
import { useAuth } from "../auth";
import { dateOnly, rupees } from "../format";
import type { ExpertPublic, Service, Subscription, SubscriptionCreated } from "../types";
import Modal from "./Modal";

type Stage = "choose" | "mock" | "paying" | "pending" | "done";

/** Joining a membership: a monthly subscription that unlocks the expert's documents. */
export default function SubscribeModal({ expert, service, onClose }: { expert: ExpertPublic; service: Service; onClose: () => void }) {
  const { me, signedIn } = useAuth();
  const queryClient = useQueryClient();
  const [stage, setStage] = useState<Stage>("choose");
  const [created, setCreated] = useState<SubscriptionCreated | null>(null);
  const [result, setResult] = useState<Subscription | null>(null);
  const [error, setError] = useState("");
  const paid = useRef(false);
  const price = rupees(service.price_paise);

  const confirm = useMutation({
    mutationFn: (body: { razorpay_payment_id?: string; razorpay_signature?: string }) => api<Subscription>(`/subscriptions/${created!.subscription.id}/pay`, { method: "POST", body }),
    onSuccess: (sub) => {
      paid.current = true;
      setResult(sub);
      setStage("done");
      for (const key of ["subs", "home", "rewards"]) queryClient.invalidateQueries({ queryKey: [key] });
    },
    onError: (e) => setError((e as Error).message),
  });

  async function openCheckout(c: SubscriptionCreated) {
    setStage("paying");
    setError("");
    try {
      await loadRazorpay();
      openRazorpay({
        key: c.payment.key_id!,
        amount: c.payment.amount_paise,
        currency: c.payment.currency,
        subscription_id: c.payment.subscription_id,
        name: "Sessio",
        description: `${service.title} (monthly)`,
        prefill: { name: me?.name, email: me?.email },
        theme: { color: "#4f46e5" },
        handler: (r) => confirm.mutate({ razorpay_payment_id: r.razorpay_payment_id, razorpay_signature: r.razorpay_signature }),
        modal: { ondismiss: () => !paid.current && setStage("pending") },
      });
    } catch (e) {
      setError((e as Error).message);
      setStage("pending");
    }
  }

  const create = useMutation({
    mutationFn: () => api<SubscriptionCreated>("/subscriptions", { method: "POST", body: { service_id: service.id } }),
    onSuccess: (c) => {
      setCreated(c);
      setError("");
      if (c.payment.mode === "mock") setStage("mock");
      else void openCheckout(c);
    },
    onError: (e) => setError((e as Error).message),
  });

  const cancel = useMutation({
    mutationFn: () => api(`/subscriptions/${created!.subscription.id}/cancel`, { method: "POST" }),
    onSuccess: onClose,
  });

  return (
    <Modal title={service.title} onClose={onClose}>
      {stage === "choose" && (
        <div className="space-y-5">
          <p className="text-sm text-slate-400">Membership by <b className="text-slate-200">{expert.name}</b></p>
          <p className="text-3xl font-extrabold">{price}<span className="text-base font-medium text-slate-400"> / month</span></p>
          {service.description && <p className="whitespace-pre-line text-sm text-slate-300">{service.description}</p>}
          <ul className="space-y-1.5 text-sm text-slate-300">
            <li>✓ Every document {expert.name} sells ({service.documents_included ?? 0} now, new ones included)</li>
            <li>✓ Cancel the renewal any time; you keep the month you paid for</li>
          </ul>
          {error && <p role="alert" className="rounded-lg border border-rose-500/30 bg-rose-500/10 px-3 py-2 text-sm text-bad">{error}</p>}
          {signedIn ? (
            <button className="btn btn-primary w-full py-3" disabled={create.isPending} onClick={() => create.mutate()}>
              {create.isPending && <Loader2 size={16} className="animate-spin" />} Subscribe for {price} / month
            </button>
          ) : (
            <Link to={`/login?next=${encodeURIComponent(`/e/${expert.handle}`)}`} className="btn btn-primary w-full py-3">Sign in to continue</Link>
          )}
        </div>
      )}

      {stage === "mock" && (
        <div className="space-y-4 text-center">
          <p className="text-4xl font-extrabold">{price}</p>
          <p className="text-sm text-slate-400">Demo payment: one month, no real money, no automatic renewal. With Razorpay keys on the server, this step opens the real Razorpay window and renews every month.</p>
          {error && <p role="alert" className="text-sm text-bad">{error}</p>}
          <button className="btn btn-primary w-full py-3" disabled={confirm.isPending} onClick={() => confirm.mutate({})}>
            {confirm.isPending && <Loader2 size={16} className="animate-spin" />} Pay {price} (demo)
          </button>
          <button className="text-sm text-slate-500 hover:text-slate-300" onClick={() => cancel.mutate()}>Cancel</button>
        </div>
      )}

      {stage === "paying" && <p className="flex items-center justify-center gap-2 py-10 text-slate-400"><Loader2 className="animate-spin" size={18} /> Opening the payment window...</p>}

      {stage === "pending" && created && (
        <div className="space-y-4 text-center">
          <p className="font-semibold text-slate-100">Payment not completed</p>
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
          <p className="text-xl font-bold">Welcome to the membership</p>
          <p className="text-sm text-slate-400">Active until {result.current_period_end ? dateOnly(result.current_period_end) : "-"}. Your documents are under Memberships.</p>
          <div className="flex gap-2 pt-2">
            <button className="btn flex-1" onClick={onClose}>Close</button>
            <Link className="btn btn-primary flex-1" to="/dashboard/memberships" onClick={onClose}>Open memberships</Link>
          </div>
        </div>
      )}
    </Modal>
  );
}
