import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";

export type Theme = "light" | "dark";

const KEY = "sessio.theme";

// Light is the default. index.html applies the saved choice before the first paint, so there is no flash.
function saved(): Theme {
  try {
    const value = localStorage.getItem(KEY);
    if (value === "light" || value === "dark") return value;
  } catch {
    /* storage can be blocked; fall back to light */
  }
  return "light";
}

interface ThemeState {
  theme: Theme;
  toggle: () => void;
}

const Ctx = createContext<ThemeState>({ theme: "light", toggle: () => {} });

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setTheme] = useState<Theme>(saved);

  useEffect(() => {
    document.documentElement.classList.toggle("dark", theme === "dark");
  }, [theme]);

  const toggle = useCallback(() => {
    const root = document.documentElement;
    root.classList.add("theme-fade"); // colors fade for a moment instead of snapping
    setTimeout(() => root.classList.remove("theme-fade"), 350);
    setTheme((current) => {
      const next: Theme = current === "dark" ? "light" : "dark";
      try {
        localStorage.setItem(KEY, next);
      } catch {
        /* the choice just will not be remembered */
      }
      return next;
    });
  }, []);

  const value = useMemo(() => ({ theme, toggle }), [theme, toggle]);
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export const useTheme = () => useContext(Ctx);
