import { CalendarCheck, Crown, Gift, House, LayoutGrid, Search, UserRound, type LucideIcon } from "lucide-react";
import { Navigate, NavLink, Outlet } from "react-router-dom";
import { useAuth } from "../../auth";
import { Avatar } from "../../components/Brand";

const ITEMS: { to: string; label: string; icon: LucideIcon }[] = [
  { to: "home", label: "Home", icon: House },
  { to: "bookings", label: "Bookings", icon: CalendarCheck },
  { to: "memberships", label: "Memberships", icon: Crown },
  { to: "find", label: "Find People", icon: Search },
  { to: "profile", label: "Profile", icon: UserRound },
  { to: "rewards", label: "Rewards", icon: Gift },
  { to: "categories", label: "Find by Category", icon: LayoutGrid },
];

/** The signed-in person's own area: a sidebar on a computer, a scrolling row of tabs on a phone. */
export default function SeekerLayout() {
  const { me, signedIn, loading } = useAuth();
  if (!signedIn) return <Navigate to="/login?next=/dashboard" replace />;
  if (loading || !me) return null;

  return (
    <div className="mx-auto grid max-w-6xl gap-6 px-4 py-8 md:grid-cols-[230px_1fr]">
      <aside className="md:sticky md:top-20 md:self-start">
        <div className="mb-3 hidden items-center gap-3 px-2 md:flex">
          <Avatar name={me.name} size={40} />
          <div className="min-w-0">
            <p className="truncate text-sm font-semibold text-slate-100">Seeker dashboard</p>
            <p className="truncate text-xs text-slate-500">{me.name}</p>
          </div>
        </div>
        <nav className="flex gap-1 overflow-x-auto md:flex-col" aria-label="Dashboard">
          {ITEMS.map(({ to, label, icon: Icon }) => (
            <NavLink
              key={to}
              to={`/dashboard/${to}`}
              className={({ isActive }) =>
                `inline-flex shrink-0 items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors ${isActive ? "bg-accent/10 text-accent" : "text-slate-400 hover:bg-ink-800 hover:text-slate-100"}`
              }
            >
              <Icon size={18} /> {label}
            </NavLink>
          ))}
        </nav>
      </aside>
      <section className="min-w-0">
        <Outlet />
      </section>
    </div>
  );
}
