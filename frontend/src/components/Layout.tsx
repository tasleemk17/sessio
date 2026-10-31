import { motion } from "framer-motion";
import { LogOut } from "lucide-react";
import { Link, NavLink, Outlet, useLocation } from "react-router-dom";
import { useAuth } from "../auth";
import { BrandMark } from "./Brand";
import ThemeToggle from "./ThemeToggle";

const link = ({ isActive }: { isActive: boolean }) =>
  `rounded-lg px-3 py-2 text-sm font-medium transition-colors ${isActive ? "bg-accent/10 text-accent" : "text-slate-400 hover:text-slate-100"}`;

export default function Layout() {
  const { me, signedIn, logout } = useAuth();
  const { pathname } = useLocation();

  return (
    <div className="min-h-screen">
      <header className="sticky top-0 z-30 border-b border-ink-800 bg-ink-950/85 backdrop-blur">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-x-4 gap-y-2 px-4 py-3">
          <Link to="/" className="flex items-center gap-2.5">
            <BrandMark />
            <span className="text-lg font-extrabold tracking-tight">Sessio</span>
          </Link>
          <nav className="order-3 flex w-full items-center gap-1 overflow-x-auto sm:order-none sm:w-auto" aria-label="Main">
            <NavLink to="/" end className={link}>
              Explore
            </NavLink>
            {signedIn && (
              <NavLink to="/dashboard" className={link}>
                My bookings
              </NavLink>
            )}
            {signedIn && (
              <NavLink to="/expert" className={link}>
                {me?.handle ? "Expert studio" : "Become an expert"}
              </NavLink>
            )}
          </nav>
          <div className="flex items-center gap-2">
            <ThemeToggle />
            {signedIn ? (
              <button onClick={logout} className="btn" title={me?.email}>
                <LogOut size={15} /> <span className="hidden sm:inline">Sign out</span>
              </button>
            ) : (
              <>
                <Link to="/login" className="btn">
                  Sign in
                </Link>
                <Link to="/login?mode=register" className="btn btn-primary hidden sm:inline-flex">
                  Get started
                </Link>
              </>
            )}
          </div>
        </div>
      </header>
      <main>
        <motion.div key={pathname} initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.25, ease: "easeOut" }}>
          <Outlet />
        </motion.div>
      </main>
      <footer className="mt-16 border-t border-ink-800 py-8 text-center text-xs text-slate-500">
        Sessio is a portfolio project. Payments run in test mode: no real money moves.
      </footer>
    </div>
  );
}
