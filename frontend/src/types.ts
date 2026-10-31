export type Kind = "call" | "document" | "dm";

export interface Me {
  id: number;
  name: string;
  email: string;
  handle: string | null;
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
}

export interface ExpertCard {
  handle: string;
  name: string;
  headline: string;
  from_paise: number | null;
  services: number;
}

export interface ExpertPublic {
  handle: string;
  name: string;
  headline: string;
  bio: string;
  timezone: string;
  services: Service[];
}

export interface ExpertMe {
  handle: string;
  headline: string;
  bio: string;
  timezone: string;
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
