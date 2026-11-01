import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Loader2 } from "lucide-react";
import { useState, type FormEvent } from "react";
import { api } from "../../api";
import { useAuth } from "../../auth";
import { useToast } from "../../components/Toast";
import type { Me } from "../../types";

function NameForm({ me }: { me: Me }) {
  const queryClient = useQueryClient();
  const toast = useToast();
  const [name, setName] = useState(me.name);
  const save = useMutation({
    mutationFn: () => api<Me>("/auth/me", { method: "PUT", body: { name } }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["me"] });
      toast("Name saved.");
    },
  });
  return (
    <form onSubmit={(e: FormEvent) => { e.preventDefault(); save.mutate(); }} className="card space-y-4 p-5">
      <h2 className="font-semibold">Your details</h2>
      <div>
        <label className="label" htmlFor="name">Name</label>
        <input id="name" className="input" value={name} minLength={2} maxLength={80} onChange={(e) => setName(e.target.value)} required />
      </div>
      <div>
        <label className="label" htmlFor="email">Email</label>
        <input id="email" className="input opacity-70" value={me.email} readOnly />
      </div>
      {save.error && <p role="alert" className="text-sm text-bad">{(save.error as Error).message}</p>}
      <button className="btn btn-primary" disabled={save.isPending || name.trim() === me.name}>{save.isPending && <Loader2 size={15} className="animate-spin" />} Save</button>
    </form>
  );
}

function PasswordForm() {
  const { adopt } = useAuth();
  const toast = useToast();
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const change = useMutation({
    mutationFn: () => api<{ token: string }>("/auth/password", { method: "POST", body: { current_password: current, new_password: next } }),
    onSuccess: (res) => {
      adopt(res.token); // this device stays signed in; every other session is signed out by the server
      setCurrent("");
      setNext("");
      toast("Password changed. Other devices were signed out.");
    },
  });
  return (
    <form onSubmit={(e: FormEvent) => { e.preventDefault(); change.mutate(); }} className="card space-y-4 p-5">
      <h2 className="font-semibold">Change password</h2>
      <div>
        <label className="label" htmlFor="cur">Current password</label>
        <input id="cur" type="password" autoComplete="current-password" className="input" value={current} onChange={(e) => setCurrent(e.target.value)} required />
      </div>
      <div>
        <label className="label" htmlFor="new">New password</label>
        <input id="new" type="password" autoComplete="new-password" className="input" value={next} minLength={10} maxLength={128} onChange={(e) => setNext(e.target.value)} required />
        <p className="mt-1 text-xs text-slate-500">At least 10 characters. A short sentence works well.</p>
      </div>
      {change.error && <p role="alert" className="text-sm text-bad">{(change.error as Error).message}</p>}
      <button className="btn btn-primary" disabled={change.isPending || !current || next.length < 10}>{change.isPending && <Loader2 size={15} className="animate-spin" />} Change password</button>
    </form>
  );
}

export default function Profile() {
  const { me, logout } = useAuth();
  if (!me) return null;
  return (
    <div className="max-w-xl space-y-5">
      <h1 className="text-3xl font-extrabold tracking-tight">Profile</h1>
      <NameForm me={me} />
      <PasswordForm />
      <button className="btn" onClick={logout}>Sign out</button>
    </div>
  );
}
