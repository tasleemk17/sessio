import { AnimatePresence, motion } from "framer-motion";
import { CheckCircle2, Info, TriangleAlert } from "lucide-react";
import { createContext, useCallback, useContext, useMemo, useRef, useState, type ReactNode } from "react";

type Kind = "success" | "error" | "info";
interface Item {
  id: number;
  kind: Kind;
  text: string;
}

const Ctx = createContext<(text: string, kind?: Kind) => void>(() => {});

const STYLE: Record<Kind, { box: string; icon: ReactNode }> = {
  success: { box: "border-emerald-500/40", icon: <CheckCircle2 size={18} className="text-ok" /> },
  error: { box: "border-rose-500/40", icon: <TriangleAlert size={18} className="text-bad" /> },
  info: { box: "border-sky-500/40", icon: <Info size={18} className="text-info" /> },
};

export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<Item[]>([]);
  const next = useRef(0);

  const push = useCallback((text: string, kind: Kind = "success") => {
    const id = ++next.current;
    setItems((list) => [...list.slice(-3), { id, kind, text }]);
    setTimeout(() => setItems((list) => list.filter((t) => t.id !== id)), 4000);
  }, []);

  const value = useMemo(() => push, [push]);
  return (
    <Ctx.Provider value={value}>
      {children}
      <div
        role="status"
        aria-live="polite"
        className="pointer-events-none fixed inset-x-4 bottom-24 z-[60] flex flex-col items-end gap-2 md:inset-x-auto md:bottom-6 md:right-6"
      >
        <AnimatePresence>
          {items.map((t) => (
            <motion.div
              key={t.id}
              layout
              initial={{ opacity: 0, y: 16, scale: 0.96 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, x: 24 }}
              transition={{ type: "spring", damping: 26, stiffness: 340 }}
              className={`pointer-events-auto flex max-w-sm items-start gap-3 rounded-xl border bg-ink-800 px-4 py-3 text-sm text-slate-100 shadow-lift ${STYLE[t.kind].box}`}
            >
              <span className="mt-0.5 shrink-0">{STYLE[t.kind].icon}</span>
              <span>{t.text}</span>
            </motion.div>
          ))}
        </AnimatePresence>
      </div>
    </Ctx.Provider>
  );
}

export const useToast = () => useContext(Ctx);
