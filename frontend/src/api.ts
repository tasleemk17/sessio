const KEY = "sessio.token";

// Empty when the website and the API share one address (Docker, dev proxy). On hosting where they are
// separate, such as Vercel plus Render, the API address is set at build time with VITE_API_BASE.
export const API_BASE: string = (import.meta.env.VITE_API_BASE ?? "").replace(/\/+$/, "");

export const tokenStore = {
  get: () => localStorage.getItem(KEY),
  set: (token: string) => localStorage.setItem(KEY, token),
  clear: () => localStorage.removeItem(KEY),
};

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function failure(res: Response): Promise<ApiError> {
  let message = res.statusText || "Something went wrong";
  try {
    const body = await res.json();
    if (typeof body.detail === "string") message = body.detail;
    else if (Array.isArray(body.detail)) message = body.detail.map((d: { msg: string }) => d.msg.replace(/^Value error, /, "")).join(", ");
  } catch {
    /* the body was not JSON */
  }
  if (res.status === 401 && tokenStore.get()) {
    tokenStore.clear(); // the session ended: send the person back to sign in
    window.dispatchEvent(new Event("sessio:logout"));
  }
  return new ApiError(res.status, message);
}

function headers(json: boolean): HeadersInit {
  const h: Record<string, string> = {};
  const token = tokenStore.get();
  if (token) h.Authorization = `Bearer ${token}`;
  if (json) h["Content-Type"] = "application/json";
  return h;
}

interface Options {
  method?: "GET" | "POST" | "PUT" | "PATCH" | "DELETE";
  body?: unknown;
  form?: FormData;
}

export async function api<T>(path: string, { method = "GET", body, form }: Options = {}): Promise<T> {
  const res = await fetch(`${API_BASE}/api${path}`, {
    method,
    headers: headers(body !== undefined),
    body: form ?? (body !== undefined ? JSON.stringify(body) : undefined),
  });
  if (!res.ok) throw await failure(res);
  return (res.status === 204 ? null : await res.json()) as T;
}

/** Downloads a protected file. A plain link cannot send the sign-in header, so the file is fetched and saved. */
export async function download(path: string, fileName: string): Promise<void> {
  const res = await fetch(`${API_BASE}/api${path}`, { headers: headers(false) });
  if (!res.ok) throw await failure(res);
  const url = URL.createObjectURL(await res.blob());
  const link = document.createElement("a");
  link.href = url;
  link.download = fileName;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

// ---------------------------------------------------------------- Razorpay Checkout

export interface RazorpayResult {
  razorpay_payment_id: string;
  razorpay_order_id: string;
  razorpay_signature: string;
}

interface RazorpayOptions {
  key: string;
  amount: number;
  currency: string;
  order_id: string;
  name: string;
  description: string;
  prefill?: { name?: string; email?: string };
  theme?: { color: string };
  handler: (result: RazorpayResult) => void;
  modal?: { ondismiss?: () => void };
}

declare global {
  interface Window {
    Razorpay?: new (options: RazorpayOptions) => { open: () => void };
  }
}

let checkoutScript: Promise<void> | null = null;

/** Loads Razorpay's script once, only when a real payment is about to start. */
export function loadRazorpay(): Promise<void> {
  if (window.Razorpay) return Promise.resolve();
  checkoutScript ??= new Promise<void>((resolve, reject) => {
    const script = document.createElement("script");
    script.src = "https://checkout.razorpay.com/v1/checkout.js";
    script.onload = () => resolve();
    script.onerror = () => {
      checkoutScript = null; // allow a retry
      reject(new Error("Could not load the payment window. Check your internet and try again."));
    };
    document.head.appendChild(script);
  });
  return checkoutScript;
}

export function openRazorpay(options: RazorpayOptions): void {
  if (!window.Razorpay) throw new Error("The payment window is not ready");
  new window.Razorpay(options).open();
}
