import { useQuery } from "@tanstack/react-query";
import { Search } from "lucide-react";
import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { api } from "../../api";
import ExpertGrid from "../../components/ExpertGrid";
import { CATEGORY_LABEL } from "../../format";
import type { CategoryInfo } from "../../types";

function useDebounced<T>(value: T, ms = 300): T {
  const [v, setV] = useState(value);
  useEffect(() => {
    const t = setTimeout(() => setV(value), ms);
    return () => clearTimeout(t);
  }, [value, ms]);
  return v;
}

/** Find People: search by name or topic, optionally inside one category. */
export function FindPeople() {
  const [params, setParams] = useSearchParams();
  const category = params.get("category") ?? "";
  const [search, setSearch] = useState("");
  const q = useDebounced(search);
  return (
    <div>
      <h1 className="text-3xl font-extrabold tracking-tight">Find People</h1>
      <div className="relative mt-5">
        <Search size={18} className="pointer-events-none absolute left-4 top-1/2 -translate-y-1/2 text-slate-500" />
        <input className="input py-3 pl-11" placeholder="Search by name or topic, e.g. AWS, resume, interviews" value={search} onChange={(e) => setSearch(e.target.value)} aria-label="Search experts" />
      </div>
      {category && (
        <p className="mt-3 text-sm text-slate-400">
          In <b className="text-slate-200">{CATEGORY_LABEL[category] ?? category}</b>{" "}
          <button className="text-accent hover:underline" onClick={() => setParams({})}>Show everyone</button>
        </p>
      )}
      <div className="mt-6"><ExpertGrid q={q} category={category} /></div>
    </div>
  );
}

/** Find by Category: every category with how many experts it has. */
export function Categories() {
  const cats = useQuery({ queryKey: ["categories"], queryFn: () => api<CategoryInfo[]>("/experts/categories") });
  return (
    <div>
      <h1 className="text-3xl font-extrabold tracking-tight">Find by Category</h1>
      <p className="mt-1 text-slate-400">Pick a topic and see the people who help with it.</p>
      {cats.isLoading && <div className="skeleton mt-6 h-40" />}
      {cats.error && <p className="mt-6 text-bad">{(cats.error as Error).message}</p>}
      <div className="mt-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {cats.data?.map((c) => (
          <Link key={c.key} to={`/dashboard/find?category=${c.key}`} className="card p-5 transition hover:-translate-y-0.5 hover:border-accent/50">
            <p className="font-semibold text-slate-100">{c.label}</p>
            <p className="mt-1 text-sm text-slate-400">{c.experts} {c.experts === 1 ? "expert" : "experts"}</p>
          </Link>
        ))}
      </div>
    </div>
  );
}
