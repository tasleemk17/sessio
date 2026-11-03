# Sessio

A marketplace where experts sell their time and knowledge, and anyone can book it. An expert gets one shareable page with six kinds of service:

- **1:1 video call**: the buyer picks a free time, pays, and gets a private video room.
- **Priority DM**: the buyer sends one question and gets a written answer.
- **Document** (products and courses): a guide or template the buyer downloads after paying.
- **Webinar or cohort**: live sessions on set dates with a seat limit. Several dates make a cohort.
- **Package**: several calls at one price. Each call is paid with a credit, and credits expire.
- **Membership**: a monthly subscription (Razorpay Subscriptions) that unlocks all of the expert's documents while it is paid up.

Payments run in **Razorpay test mode** (or a built-in demo mode with no account), so no real money ever moves.

![Home](docs/screenshots/home-light.png)

![Expert page](docs/screenshots/expert-page-light.png)

## What it does

| For buyers | For experts |
|---|---|
| Search experts by name, topic or category | Create a page in a minute (`/e/your-name`) |
| Pick a day and time, shown in your own time zone | Add any of the six services with their prices |
| Pay, then get the video link, the file or the answer | Set weekly hours once; free times are worked out for you |
| Seeker dashboard: Home, Bookings (1:1 calls, Priority DM, Products/Courses, Webinars & Cohorts, Packages), Memberships, Find People, Profile, Rewards, Find by Category | Studio: earnings (memberships included), orders, a reply box for DMs |

## How it is built

**Backend**: FastAPI, SQLAlchemy, pydantic v2. SQLite by default, Postgres with one `DATABASE_URL`. Login with JWT and pbkdf2 password hashes.
**Frontend**: React 19, TypeScript, Tailwind, react-query, light and dark themes.

Decisions worth reading:

- **No double booking.** A unique constraint on the call slot is the real guard, so two people paying at the same instant cannot both get it. The loser sees a clear message and fresh times.
- **Hold, then pay.** Choosing a time holds it for 15 minutes. If payment never completes, the time is free again.
- **Time zones.** Experts set weekly hours in their own zone. Slots are computed to UTC and shown in each viewer's zone.
- **Money in paise** (integers), never floats.
- **Payments verified on the server.** The server creates the Razorpay order; the browser opens Checkout with only the public key; the server checks the HMAC-SHA256 signature of `order_id|payment_id` with the secret before confirming. Without keys the same flow runs in demo mode.
- **Safe downloads.** Files are served as attachments with `application/octet-stream` and `nosniff`, only to the buyer who paid and to the seller. Uploads need a seller declaration (own the file, no one else's personal contact details).
- **Security is built in, not added on.** Strong password hashing, brute-force lockout, forged-token rejection, content-checked uploads, CSP and other headers, strict CORS, a signed Razorpay webhook, and a production mode that refuses to start with unsafe settings. Everything is listed, with the test that proves it, in [docs/SECURITY.md](docs/SECURITY.md).
- **Seats and credits cannot be oversold.** A webinar's seats are counted while its row is locked, and a package's last credit is locked the same way, so two people paying at once cannot both get it.
- **Memberships follow the money.** Access lasts until the paid month ends, even after cancelling. Razorpay's signed webhook extends it on every monthly charge.
- **Tests.** 91 tests cover accounts, slot maths, double booking, holds, documents, DMs, webinars, packages, memberships, rewards, payment verification and the security rules. They also pass on Postgres (`TEST_DATABASE_URL`).

## On a phone

The site is built for phones first: no sideways scrolling at 375 px wide, the dashboard menu scrolls along its own row, booking windows slide up from the bottom like a phone sheet, and inputs are 16 px so iPhones do not zoom in when you tap them. Razorpay's checkout and the Jitsi video rooms both open fine in a mobile browser.

Once the site is online (https), people can install it like an app: Android Chrome shows "Install app" or "Add to Home screen", and on iPhone Safari use Share > Add to Home Screen. It opens full screen with the Sessio icon. There is no offline mode: it needs internet, as a booking site should.

## Run it

You need Python 3.13 and Node 22.

```bash
cd backend
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements-dev.txt
.venv/Scripts/python -m uvicorn app.main:app --port 8010
```

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5190. With no keys set, payments use the demo button (laptop only: on a public site it would let anyone book for free, so production refuses it unless you switch it on on purpose).

### Demo data

With the API running on a fresh local database, this fills it with three experts (every kind of service) and a buyer who has bought some of each. Local use only: the passwords are public.

```bash
cd backend
.venv/Scripts/python scripts/seed_demo.py
```

Then sign in as `ravi@example.test` (buyer) or `asha@example.test` (expert) with the password `demo-pass-phrase-1`.

### Real Razorpay (test mode)

Create a free Razorpay account, switch to Test Mode, generate test keys, and put them in `.env` (copy `.env.example`):

```
RAZORPAY_KEY_ID=rzp_test_...
RAZORPAY_KEY_SECRET=...
```

Restart the API. Booking now opens the Razorpay window; use Razorpay's published test cards. Keep the secret out of Git: `.env` is ignored.

For payments to be confirmed even when the buyer closes the tab, add the webhook described in [docs/SECURITY.md](docs/SECURITY.md#setting-up-the-razorpay-webhook-recommended-for-any-real-use).

### Docker

```bash
cp .env.example .env   # then set JWT_SECRET
docker compose up --build
```

Site on http://localhost:5190.

### Tests

```bash
cd backend
.venv/Scripts/python -m pytest -q
```

## Deploy for free

Vercel (site) + Render (API) + Neon (Postgres): see [docs/DEPLOY.md](docs/DEPLOY.md).

## Scope and honest limits

- Test-mode payments only; nothing is paid out to experts. The 10% platform fee is shown in earnings for demonstration.
- No refunds or buyer cancellation of paid bookings yet. No email verification, password reset or two-factor sign-in (see the limits in [docs/SECURITY.md](docs/SECURITY.md)).
- Files are stored in the database (limit 5 MB each), fine for a demo; a real product would use object storage.
- Rewards earn points (1 per ₹10) and show a level; spending points is not built yet.
- Memberships with real Razorpay billing are covered by tests that fake Razorpay's network calls (signature checks, webhooks, cancelling). They have not been run against Razorpay's servers, so try one in test mode before relying on it.
- There is no migration tool: the tables are created on startup. After pulling a version that adds columns, recreate a local database (delete `backend/sessio.db`).
- Sessio does not list or sell anyone's personal phone numbers or contact details, and uploads that do are against the seller declaration.
