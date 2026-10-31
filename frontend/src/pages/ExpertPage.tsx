import { useQuery } from "@tanstack/react-query";
import { Clock, FileText, Globe, MessageSquareText, Video } from "lucide-react";
import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../api";
import BookingModal from "../components/BookingModal";
import { Avatar } from "../components/Brand";
import { KIND_LABEL, rupees } from "../format";
import type { ExpertPublic, Service } from "../types";

const ICON = { call: Video, document: FileText, dm: MessageSquareText } as const;
const ACTION = { call: "Book a time", document: "Buy now", dm: "Ask a question" } as const;

function detail(s: Service): string {
  if (s.kind === "call") return `${s.duration_min} minutes, on video`;
  if (s.kind === "dm") return `Written reply within ${s.reply_hours} hours`;
  return s.file_name ? "Instant download after you pay" : "File coming soon";
}

export default function ExpertPage() {
  const { handle = "" } = useParams();
  const [chosen, setChosen] = useState<Service | null>(null);
  const page = useQuery({ queryKey: ["expert", handle], queryFn: () => api<ExpertPublic>(`/experts/${handle}`) });

  if (page.isLoading) return <div className="mx-auto max-w-3xl px-4 py-10"><div className="skeleton h-64" /></div>;
  if (page.error || !page.data) {
    return (
      <div className="mx-auto max-w-md px-4 py-20 text-center">
        <p className="text-xl font-semibold">We could not find that page</p>
        <p className="mt-1 text-sm text-slate-400">{(page.error as Error | null)?.message}</p>
        <Link to="/" className="btn mt-5">
          Back to Explore
        </Link>
      </div>
    );
  }
  const expert = page.data;

  return (
    <div className="mx-auto max-w-3xl px-4 py-10">
      <header className="flex flex-col items-start gap-4 sm:flex-row sm:items-center">
        <Avatar name={expert.name} size={84} />
        <div>
          <h1 className="text-3xl font-extrabold tracking-tight">{expert.name}</h1>
          {expert.headline && <p className="mt-1 text-lg text-slate-400">{expert.headline}</p>}
          <p className="mt-2 inline-flex items-center gap-1.5 text-xs text-slate-500">
            <Globe size={13} /> Available in {expert.timezone.replace("_", " ")} time
          </p>
        </div>
      </header>
      {expert.bio && <p className="mt-6 whitespace-pre-line leading-relaxed text-slate-300">{expert.bio}</p>}

      <h2 className="mb-3 mt-10 text-lg font-semibold">Services</h2>
      {expert.services.length === 0 && <div className="card p-8 text-center text-slate-400">Nothing is on offer right now.</div>}
      <div className="space-y-3">
        {expert.services.map((s) => {
          const Icon = ICON[s.kind];
          const unavailable = s.kind === "document" && !s.file_name;
          return (
            <article key={s.id} className="card flex flex-col gap-4 p-5 sm:flex-row sm:items-center">
              <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-accent/10 text-accent">
                <Icon size={21} />
              </span>
              <div className="min-w-0 flex-1">
                <p className="flex flex-wrap items-center gap-2 font-semibold text-slate-100">
                  {s.title} <span className="chip">{KIND_LABEL[s.kind]}</span>
                </p>
                {s.description && <p className="mt-1 text-sm text-slate-400">{s.description}</p>}
                <p className="mt-1.5 inline-flex items-center gap-1.5 text-xs text-slate-500">
                  <Clock size={12} /> {detail(s)}
                </p>
              </div>
              <div className="flex items-center justify-between gap-4 sm:flex-col sm:items-end">
                <span className="text-xl font-bold text-slate-100">{rupees(s.price_paise)}</span>
                <button className="btn btn-primary" onClick={() => setChosen(s)} disabled={unavailable}>
                  {unavailable ? "Not ready" : ACTION[s.kind]}
                </button>
              </div>
            </article>
          );
        })}
      </div>

      {chosen && <BookingModal expert={expert} service={chosen} onClose={() => setChosen(null)} />}
    </div>
  );
}
