import { Mail, MapPin, Phone } from "lucide-react";
import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import { BUSINESS as B } from "../business";

function Page({ title, children }: { title: string; children: ReactNode }) {
  return (
    <article className="mx-auto max-w-3xl px-4 py-12">
      <h1 className="text-3xl font-extrabold tracking-tight">{title}</h1>
      <p className="mt-2 text-sm text-slate-500">Last updated: {B.lastUpdated}</p>
      <div className="mt-8 space-y-6 leading-relaxed text-slate-300">{children}</div>
    </article>
  );
}

function H({ children }: { children: ReactNode }) {
  return <h2 className="pt-2 text-lg font-semibold text-slate-100">{children}</h2>;
}

const email = <a className="text-accent hover:underline" href={`mailto:${B.supportEmail}`}>{B.supportEmail}</a>;

export function Contact() {
  return (
    <Page title="Contact us">
      <p>
        {B.brand} is run by {B.owner}. For questions about a booking, a payment, a refund or your account, write to us and we
        reply within 1 to 2 working days.
      </p>
      <div className="card space-y-4 p-6">
        <p className="flex items-center gap-3"><Mail size={18} className="text-accent" /> {email}</p>
        {B.supportPhone && <p className="flex items-center gap-3"><Phone size={18} className="text-accent" /> {B.supportPhone}</p>}
        <p className="flex items-center gap-3"><MapPin size={18} className="text-accent" /> {B.city}</p>
      </div>
      <p>When you write about an order, please include the email you signed in with and the booking number from <Link className="text-accent hover:underline" to="/dashboard/bookings">My bookings</Link>.</p>
    </Page>
  );
}

export function Terms() {
  return (
    <Page title="Terms and conditions">
      <p>
        These terms apply to everyone who uses {B.brand} ("we", "us"), a website operated by {B.owner}, {B.city}. By creating an
        account or paying for a service you agree to them.
      </p>
      <H>What we offer</H>
      <p>
        {B.brand} sells online career services: 1:1 video calls, written answers to questions (Priority DM) and downloadable
        guides. The price, length and contents of each service are shown on its page before you pay.
      </p>
      <H>Accounts</H>
      <p>You need an account to buy. Keep your password private; you are responsible for what is done with your account.</p>
      <H>Payments</H>
      <p>
        Prices are in Indian Rupees (INR) and include all charges shown at checkout. Payments are processed by Razorpay; we never
        see or store your card, UPI or bank details.
      </p>
      <H>Delivery of services</H>
      <ul className="list-disc space-y-1 pl-6">
        <li>Video call: the meeting link appears in My bookings right after payment and is used at the booked time.</li>
        <li>Priority DM: the written answer appears in My bookings within the reply time shown on the service.</li>
        <li>Guide or document: available to download from My bookings immediately after payment.</li>
      </ul>
      <p>Nothing is shipped physically.</p>
      <H>No guaranteed outcome</H>
      <p>
        Our guidance is advice based on experience. We do not promise a job, an interview, a referral or any particular result,
        and we never charge a fee for placing you in a job.
      </p>
      <H>Cancellations and refunds</H>
      <p>See our <Link className="text-accent hover:underline" to="/refund-policy">Refund and cancellation policy</Link>.</p>
      <H>Fair use</H>
      <p>
        Downloaded guides are for your personal use. Do not resell, share publicly or copy them. Do not record a call without the
        other person's consent, and do not use the service for anything unlawful or abusive.
      </p>
      <H>Liability</H>
      <p>
        To the extent the law allows, our total liability for any claim about a service is limited to the amount you paid for that
        service.
      </p>
      <H>Changes and governing law</H>
      <p>
        We may update these terms; the date above shows the latest version. These terms are governed by the laws of India, and the
        courts of {B.jurisdiction} have jurisdiction. Questions: {email}.
      </p>
    </Page>
  );
}

export function Privacy() {
  return (
    <Page title="Privacy policy">
      <p>This policy explains what {B.brand} collects, why, and the choices you have.</p>
      <H>What we collect</H>
      <ul className="list-disc space-y-1 pl-6">
        <li>Account details: your name, email and password (stored only as a one-way hash, never readable).</li>
        <li>Order details: what you booked or bought, the time, the amount, and the questions you send.</li>
        <li>Files an expert uploads for sale.</li>
        <li>Basic technical logs (such as IP address and time of a request) used to keep the site secure and stop abuse.</li>
      </ul>
      <H>Payments</H>
      <p>
        Payments are handled by Razorpay. Your card, UPI and bank details go directly to Razorpay and are never stored by us. We
        keep only the payment reference and the amount.
      </p>
      <H>How we use it</H>
      <p>To run your account, deliver what you paid for, answer support requests, prevent fraud and meet legal obligations. We do not sell your data and do not use it for third-party advertising.</p>
      <H>Who processes it</H>
      <p>The site runs on Vercel (website), Render (server) and Neon (database), and payments on Razorpay. They process data only to provide their service to us.</p>
      <H>Cookies and storage</H>
      <p>We use your browser's local storage to keep you signed in and to remember your light or dark theme. We do not use advertising or tracking cookies.</p>
      <H>Your choices</H>
      <p>You can ask us to see, correct or delete your data by writing to {email}. We keep payment records for as long as Indian tax and accounting law requires.</p>
    </Page>
  );
}

export function RefundPolicy() {
  return (
    <Page title="Refund and cancellation policy">
      <p>We want every session to be worth it. This is how cancellations and refunds work on {B.brand}.</p>
      <H>1:1 video calls</H>
      <ul className="list-disc space-y-1 pl-6">
        <li>Cancel at least {B.cancelHours} hours before the call: full refund.</li>
        <li>Cancel less than {B.cancelHours} hours before, or not join: no refund.</li>
        <li>If the expert cancels or does not join: full refund, or a new time if you prefer.</li>
        <li>If the time you paid for was taken by someone else at the same moment: full refund.</li>
      </ul>
      <H>Priority DM (written answer)</H>
      <ul className="list-disc space-y-1 pl-6">
        <li>If no answer arrives within the reply time shown on the service: full refund.</li>
        <li>Once the answer has been delivered, it is not refundable.</li>
      </ul>
      <H>Guides and documents</H>
      <ul className="list-disc space-y-1 pl-6">
        <li>Digital downloads are not refundable once downloaded.</li>
        <li>If the file is wrong, broken or does not match its description, we will send the right file or refund you in full.</li>
      </ul>
      <H>How to ask for a refund</H>
      <p>
        Write to {email} with the email you signed in with and your booking number. We reply within 1 to 2 working days. Approved
        refunds are sent back to the original payment method through Razorpay within {B.refundDays} working days; your bank may
        take a few more days to show it.
      </p>
      <H>Delivery</H>
      <p>All services are delivered online through My bookings, as described in our <Link className="text-accent hover:underline" to="/terms">Terms</Link>. Nothing is shipped.</p>
    </Page>
  );
}
