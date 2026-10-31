import { Eye, EyeOff } from "lucide-react";
import { useState, type FormEvent } from "react";
import { Navigate, useNavigate, useSearchParams } from "react-router-dom";
import { useAuth } from "../auth";
import { useServerWake } from "../useServerWake";

export default function Login() {
  const { submit, signedIn } = useAuth();
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const { waking } = useServerWake();
  const [mode, setMode] = useState<"login" | "register">(params.get("mode") === "register" ? "register" : "login");
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [show, setShow] = useState(false);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  // Only paths on this site are accepted as the place to return to, never another address
  const next = params.get("next");
  const target = next && next.startsWith("/") && !next.startsWith("//") && !next.includes("\\") ? next : "/dashboard";
  if (signedIn) return <Navigate to={target} replace />;

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError("");
    setBusy(true);
    try {
      await submit(mode, mode === "register" ? { name: name.trim(), email: email.trim(), password } : { email: email.trim(), password });
      navigate(target, { replace: true });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not sign in");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto flex min-h-[70vh] max-w-sm items-center px-4">
      <form onSubmit={onSubmit} className="w-full">
        <h1 className="text-2xl font-bold">{mode === "login" ? "Welcome back" : "Create your account"}</h1>
        <p className="mt-1 text-sm text-slate-400">{mode === "login" ? "Sign in to see your bookings." : "One account to book people, and to be booked."}</p>

        {mode === "register" && (
          <>
            <label className="label mt-6" htmlFor="name">
              Your name
            </label>
            <input id="name" className="input" value={name} onChange={(e) => setName(e.target.value)} required minLength={2} autoComplete="name" />
          </>
        )}
        <label className="label mt-4" htmlFor="email">
          Email
        </label>
        <input id="email" type="email" className="input" value={email} onChange={(e) => setEmail(e.target.value)} required autoComplete="email" />

        <label className="label mt-4" htmlFor="password">
          Password
        </label>
        <div className="relative">
          <input
            id="password"
            type={show ? "text" : "password"}
            className="input pr-10"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            minLength={8}
            autoComplete={mode === "login" ? "current-password" : "new-password"}
          />
          <button type="button" onClick={() => setShow(!show)} className="absolute right-2 top-1/2 -translate-y-1/2 rounded p-1 text-slate-500 hover:text-slate-200" aria-label={show ? "Hide password" : "Show password"}>
            {show ? <EyeOff size={16} /> : <Eye size={16} />}
          </button>
        </div>
        {mode === "register" && <p className="mt-1.5 text-xs text-slate-500">At least 10 characters. A short sentence works well.</p>}

        {waking && (
          <p role="status" className="mt-4 rounded-lg border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-sm text-warn">
            The server was asleep and is starting up. Free hosting does this when nobody has visited for a while. It takes up to a minute.
          </p>
        )}
        {error && (
          <p role="alert" className="mt-4 rounded-lg border border-rose-500/30 bg-rose-500/10 px-3 py-2 text-sm text-bad">
            {error}
          </p>
        )}

        <button className="btn btn-primary mt-6 w-full" disabled={busy}>
          {busy ? "Please wait..." : mode === "login" ? "Sign in" : "Create account"}
        </button>
        <button
          type="button"
          className="mt-4 w-full text-center text-sm text-slate-400 hover:text-slate-200"
          onClick={() => {
            setMode(mode === "login" ? "register" : "login");
            setError("");
          }}
        >
          {mode === "login" ? "New here? Create an account" : "Already have an account? Sign in"}
        </button>
      </form>
    </div>
  );
}
