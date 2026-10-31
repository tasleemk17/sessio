import { motion } from "framer-motion";
import { X } from "lucide-react";
import { useEffect, type ReactNode } from "react";

/** A dialog that closes with Escape or a click outside, and slides up from the bottom on a phone. */
export default function Modal({ title, onClose, children, wide = false }: { title: string; onClose: () => void; children: ReactNode; wide?: boolean }) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    document.body.style.overflow = "hidden";
    return () => {
      window.removeEventListener("keydown", onKey);
      document.body.style.overflow = "";
    };
  }, [onClose]);

  return (
    <motion.div
      className="fixed inset-0 z-50 flex items-end justify-center bg-slate-900/50 backdrop-blur-sm dark:bg-black/70 sm:items-center sm:p-4"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      onClick={onClose}
    >
      <motion.div
        role="dialog"
        aria-label={title}
        aria-modal="true"
        onClick={(e) => e.stopPropagation()}
        initial={{ y: 40, opacity: 0 }}
        animate={{ y: 0, opacity: 1 }}
        transition={{ type: "spring", damping: 28, stiffness: 320 }}
        className={`card flex max-h-[92vh] w-full flex-col rounded-b-none sm:rounded-2xl ${wide ? "max-w-2xl" : "max-w-lg"}`}
      >
        <header className="flex items-center justify-between border-b border-ink-700 px-5 py-4">
          <h2 className="text-lg font-semibold text-slate-100">{title}</h2>
          <button onClick={onClose} className="rounded-lg p-1.5 text-slate-400 hover:bg-ink-800 hover:text-slate-200" aria-label="Close">
            <X size={18} />
          </button>
        </header>
        <div className="overflow-y-auto overscroll-contain p-5">{children}</div>
      </motion.div>
    </motion.div>
  );
}
