export type Kind = "call" | "document" | "dm" | "webinar" | "package" | "membership";
export type Category = "career" | "tech" | "interview" | "finance" | "design" | "marketing" | "health" | "education" | "other";

export interface Me {
  id: number;
  name: string;
  email: string;
  handle: string | null;
  /** Whether this person may create an expert page. On a single-expert site only the owner can. */
  can_be_expert?: boolean;
}

export interface Service {
  id: number;
  kind: Kind;
  title: string;
  description: string;
  price_paise: number;
  duration_min: number | null;
  reply_hours: number | null;
  is_active: boolean;
  file_name: string | null;
  file_size: number | null;
  capacity: number | null;
  spots_left: number | null;
  sessions: string[];
  call_service_id: number | null;
  call_service_title: string | null;
  credits: number | null;
  valid_days: number | null;
  documents_included: number | null;
}

export interface ExpertCard {
  handle: string;
  name: string;
  headline: string;
  category: Category;
  from_paise: number | null;
  services: number;
}

export interface ExpertPublic {
  handle: string;
  name: string;
  headline: string;
  bio: string;
  timezone: string;
  category: Category;
  services: Service[];
}

export interface ExpertMe {
  handle: string;
  headline: string;
  bio: string;
  timezone: string;
  category: Category;
}

export interface Booking {
  id: number;
  kind: Kind;
  status: "pending" | "paid" | "cancelled" | "expired";
  amount_paise: number;
  slot_start: string | null;
  slot_end: string | null;
  note: string;
  answer: string | null;
  meeting_link: string | null;
  created_at: string;
  paid_at: string | null;
  answered_at: string | null;
  service_title: string;
  expert_name: string;
  expert_handle: string;
  seeker_name: string | null;
  has_file: boolean;
  file_name: string | null;
  file_size: number | null;
  service_id: number;
  reference: string;
  sessions: string[];
  package_total: number | null;
  package_used: number | null;
  package_call_service_id: number | null;
  valid_until: string | null;
  via_package: boolean;
}

export interface PaymentInfo {
  mode: "razorpay" | "mock";
  order_id: string;
  key_id: string | null;
  amount_paise: number;
  currency: string;
}

export interface BookingCreated {
  booking: Booking;
  payment: PaymentInfo | null;
}

export interface Subscription {
  id: number;
  status: "pending" | "active" | "cancelling" | "cancelled" | "expired";
  service_id: number;
  service_title: string;
  expert_name: string;
  expert_handle: string;
  amount_paise: number;
  payments: number;
  created_at: string;
  current_period_end: string | null;
  cancel_at_period_end: boolean;
  has_access: boolean;
  documents_included: number;
}

export interface SubscriptionCreated {
  subscription: Subscription;
  payment: { mode: "razorpay" | "mock"; subscription_id: string; key_id: string | null; amount_paise: number; currency: string };
}

export interface CategoryInfo {
  key: Category;
  label: string;
  experts: number;
}

export interface Rewards {
  points: number;
  spent_paise: number;
  tier: string;
  next_tier: string | null;
  points_to_next: number | null;
  recent: { title: string; points: number; at: string }[];
}

export interface HomeSummary {
  name: string;
  upcoming_calls: number;
  upcoming_webinars: number;
  documents: number;
  pending_replies: number;
  active_memberships: number;
  active_packages: number;
  next_session: Booking | null;
}

export interface Slots {
  timezone: string;
  duration_min: number;
  slots: string[];
}

export interface Summary {
  orders: number;
  gross_paise: number;
  fee_paise: number;
  net_paise: number;
  fee_percent: number;
  by_kind: Record<string, number>;
  pending_dms: number;
  upcoming_calls: number;
}

export interface Window {
  weekday: number;
  start_min: number;
  end_min: number;
}
