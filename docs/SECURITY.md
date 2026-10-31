# Security

What Sessio protects, how, and what it does not do yet. It handles accounts, bookings and (test-mode) payments, so each decision below has a reason and a test.

## What is protected

| Risk | What the code does | Test |
|---|---|---|
| Stolen password database | Passwords are never stored. PBKDF2-HMAC-SHA256, 600,000 rounds, random salt per user. The round count is stored with each hash, so it can be raised later and old hashes upgrade at the next sign-in. | `test_hashes_are_salted...`, `test_an_old_hash_still_works...` |
| Weak passwords | At least 10 characters, not on a common list, not mostly one repeated character, must not contain the email name. | `test_weak_passwords_are_refused` |
| Guessing passwords | 5 wrong tries per email and address lock that pair for 15 minutes (even the right password waits). 20 logins a minute per address. 10 sign-ups an hour per address. A stranger's failures count against the stranger's address, so they cannot lock you out. | `test_repeated_wrong_passwords...`, `test_a_stranger_cannot_lock_you_out...` |
| Finding out who has an account | Login gives one message for "no account" and "wrong password", and spends the same hashing time for both. | `test_login_does_not_reveal...` |
| Forged sessions | Signed JWT. The algorithm is pinned (a token cannot ask for `none`), expiry is required, tokens last 24 hours. | `test_forged_and_broken_tokens_are_refused` |
| Paying nothing | Payment is confirmed only after the server verifies Razorpay's HMAC signature with the secret key. Amounts come from the server, never the browser. A "demo payment" mode exists for laptops but **production refuses to start with it on unless `ALLOW_MOCK_PAYMENTS=true` is set on purpose**. | `test_a_site_without_payments...`, `test_browser_confirmation_needs_a_valid_signature` |
| Browser closed mid-payment | Razorpay's webhook confirms the payment from their side. The signature is checked over the raw bytes, the paid amount must equal the booking price, and repeats change nothing. | `test_webhook_*` |
| Double booking | A unique database constraint on the call slot, not just a check in code. | `test_bookings.py` |
| Hoarding every time slot | One person can hold at most 3 unpaid bookings; holds expire after 15 minutes. | `test_one_person_cannot_hold_every_time` |
| Reading someone else's data | Every booking, file and message is looked up by owner. Other people's rows answer 404, so their existence is not confirmed. | `test_nobody_can_touch_someone_elses_booking` |
| Malicious uploads | Allow-list of extensions, 5 MB cap, the first bytes must match the claimed type, programs (`MZ`, ELF, `#!`) are refused, names are sanitised. Files are served only as `application/octet-stream` attachments with `nosniff`, so a file can never run as a web page. The seller must declare they own it and that it holds nobody's personal contact details. | `test_a_program_cannot_hide...` |
| Huge requests | JSON bodies over 64 KB and uploads over 5 MB are refused while they arrive, including bodies sent in chunks. nginx also limits at 6 MB. | `test_oversized_bodies_are_refused` |
| Cross-site scripts and framing | The site is served with a Content-Security-Policy (scripts only from itself and Razorpay), `X-Frame-Options: DENY`, `nosniff`, a strict referrer policy. There are no inline scripts. The API sends `no-store` and a policy that lets nothing load. | `test_responses_carry_security_headers` |
| Other websites calling the API | CORS allows exactly the addresses in `CORS_ORIGINS`, never `*`, only the methods and headers the site uses. | `test_only_the_listed_site...` |
| Search abuse | `%` and `_` typed into search are plain characters. Query length is capped. SQL is always parameterised through SQLAlchemy. | `test_search_wildcards_are_plain_characters` |
| Unsafe production setup | With `ENVIRONMENT=production` the API refuses to start with a weak or default `JWT_SECRET`, `*` in CORS, plain-http origins, half-set Razorpay keys, no payment method, or SQLite. `/docs` and the schema are switched off. | `test_production_refuses_unsafe_settings` |
| Leaking secrets | Keys come from environment variables. `.env` is git-ignored. Logs never include passwords, tokens or Razorpay responses. Dependencies were scanned: no known vulnerabilities (`pip-audit`, `npm audit`), and CI repeats the scan. | CI |

## Setting up the Razorpay webhook (recommended for any real use)

1. Razorpay dashboard (Test Mode) > Settings > Webhooks > Add new webhook.
2. URL: `https://<your-api>/api/payments/webhook`
3. Secret: make up a long random one and set it as `RAZORPAY_WEBHOOK_SECRET` on the server.
4. Events: `payment.captured` and `order.paid`.

## Known limits (honest list)

- **The login token lives in the browser's local storage.** If an attacker could run script on the site, they could read it. That is why the CSP forbids inline and foreign scripts and why React escapes all text. A stricter design uses an `HttpOnly` cookie plus CSRF protection; it is the next step if the site is ever served on one domain only.
- **Rate limits are in memory, per server process.** Right for one server (the free plan runs one). With several servers they need a shared store such as Redis.
- **No email verification, password reset, or two-factor sign-in.** Without email delivery there is no safe way to recover an account yet, so none is offered rather than a weak one.
- **No refunds or buyer cancellation of paid bookings,** and no payouts to experts. Money in this project is test money.
- **Files are not scanned for malware** and are stored in the database. They are only ever offered as downloads, but a buyer should still treat a downloaded file as untrusted. Real products use object storage and a scanner.
- **Video rooms (Jitsi) are protected only by an unguessable name** (48 random bits). Anyone with the link can join.
- **Sign-up reveals whether an email is taken** (it must, to tell the person). It is rate limited.

## Reporting a problem

Open a private security advisory on the GitHub repository. Please do not post exploits in public issues.
