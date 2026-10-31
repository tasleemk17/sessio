import { useQuery } from "@tanstack/react-query";
import { CalendarClock, FileText, MessageSquareText, Search } from "lucide-react";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import { Avatar } from "../components/Brand";
import { rupees } from "../format";
import type { ExpertCard } from "../types";

function useDebounced<T>(value: T, ms = 300): T {
  const [v, setV] = useState(value);
  useEffect(() => {
    const t = setTimeout(() => setV(value), ms);
    return () => clearTimeout(t);
  }, [value, ms]);
  return v;
}

const STEPS = [
  { icon: Search, title: "Find someone who has done it", text: "Search by name or topic. Every expert has a page with clear prices." },
  { icon: CalendarClock, title: "Book, buy or ask", text: "Pick a time for a 1:1 call, buy a guide, or send a question for a written reply." },
  { icon: FileText, title: "Get it in your dashboard", text: "Your meeting link, your downloads and your answers wait in one place." },
];

export default function Home() {
  const [search, setSearch] = useState("");
  const q = useDebounced(search);
  const experts = useQuery({ queryKey: ["experts", q], queryFn: () => api<ExpertCard[]>(`/experts?q=${encodeURIComponent(q)}`), placeholderData: (prev) => prev });

  return (
    <div>
      <section className="mx-auto max-w-6xl px-4 pb-8 pt-14 text-center sm:pt-20">
        <h1 className="mx-auto max-w-3xl text-4xl font-extrabold tracking-tight sm:text-6xl">
          Get an hour with people who <span className="text-gradient">have been there</span>
        </h1>
        <p className="mx-auto mt-5 max-w-xl text-lg text-slate-400">Book a call, buy a guide, or ask one question and get a written answer. Careers, certificates, interviews and more.</p>
        <div className="relative mx-auto mt-8 max-w-xl">
          <Search size={18} className="pointer-events-none absolute left-4 top-1/2 -translate-y-1/2 text-slate-500" />
          <input className="input py-3.5 pl-11 text-base" placeholder="Search by name or topic, e.g. AWS, resume, interviews" value={search} onChange={(e) => setSearch(e.target.value)} aria-label="Search experts" />
        </div>
      </section>

      <section className="mx-auto max-w-6xl px-4">
        <h2 className="mb-4 text-xl font-semibold">{q ? `Results for "${q}"` : "Experts"}</h2>
        {experts.isLoading && (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {Array.from({ length: 3 }, (_, i) => (
              <div key={i} className="skeleton h-40" />
            ))}
          </div>
        )}
        {experts.error && <p className="text-bad">{(experts.error as Error).message}</p>}
        {experts.isSuccess && experts.data.length === 0 && (
          <div className="card px-6 py-14 text-center">
            <p className="font-semibold text-slate-200">{q ? "No expert matches that yet" : "No experts have joined yet"}</p>
            <p className="mt-1 text-sm text-slate-400">Be the first: create your page and add a service.</p>
            <Link to="/expert" className="btn btn-primary mt-5">
              Become an expert
            </Link>
          </div>
        )}
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {experts.data?.map((e) => (
            <Link key={e.handle} to={`/e/${e.handle}`} className="card group p-5 transition hover:-translate-y-0.5 hover:border-accent/50 hover:shadow-lift">
              <div className="flex items-center gap-3">
                <Avatar name={e.name} />
                <div className="min-w-0">
                  <p className="truncate font-semibold text-slate-100">{e.name}</p>
                  <p className="truncate text-xs text-slate-500">/e/{e.handle}</p>
                </div>
              </div>
              <p className="mt-3 line-clamp-2 min-h-10 text-sm text-slate-400">{e.headline || "No headline yet"}</p>
              <div className="mt-4 flex items-center justify-between text-sm">
                <span className="text-slate-500">{e.services} {e.services === 1 ? "service" : "services"}</span>
                {e.from_paise !== null && <span className="font-semibold text-accent">{e.from_paise === 0 ? "Free options" : `from ${rupees(e.from_paise)}`}</span>}
              </div>
            </Link>
          ))}
        </div>
      </section>

      <section className="mx-auto mt-16 max-w-6xl px-4">
        <h2 className="mb-6 text-center text-2xl font-bold">How it works</h2>
        <div className="grid gap-4 sm:grid-cols-3">
          {STEPS.map(({ icon: Icon, title, text }, i) => (
            <div key={title} className="card p-5">
              <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-accent/10 text-accent">
                <Icon size={20} />
              </span>
              <p className="mt-4 font-semibold text-slate-100">
                {i + 1}. {title}
              </p>
              <p className="mt-1 text-sm text-slate-400">{text}</p>
            </div>
          ))}
        </div>
        <div className="card mt-8 flex flex-col items-center gap-3 bg-gradient-to-br from-accent/10 to-transparent px-6 py-10 text-center">
          <MessageSquareText className="text-accent" />
          <h3 className="text-xl font-bold">Know something people ask you about?</h3>
          <p className="max-w-md text-sm text-slate-400">Create your page in a minute, set a price, choose your hours, and share one link.</p>
          <Link to="/expert" className="btn btn-primary">
            Create your expert page
          </Link>
        </div>
      </section>
    </div>
  );
}
