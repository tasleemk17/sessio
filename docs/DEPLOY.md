# Deploy Sessio free

Three free services: **Neon** (database), **Render** (API), **Vercel** (website). Do them in this order.

## 1. Neon: the database

1. Create a project at neon.tech.
2. Copy the connection string (it starts with `postgresql://`). Keep it private.

## 2. Render: the API

1. New > Blueprint, choose this repository. Render reads `render.yaml`.
2. When asked, fill in:
   - `DATABASE_URL`: the Neon string.
   - `CORS_ORIGINS`: your Vercel address (you get it in step 3; you can set it afterwards under Environment).
   - `RAZORPAY_KEY_ID` / `RAZORPAY_KEY_SECRET`: your Razorpay **test** keys.
   - `RAZORPAY_WEBHOOK_SECRET`: a long random secret you also type into Razorpay's webhook form (step 4).
   - `ALLOW_MOCK_PAYMENTS` stays `false`. Only if you want a public demo with no Razorpay account, set it to `true`, and say on the site that it is a demo: anybody can then "book" for free.
3. The API starts in `production` mode and refuses to run with a weak secret, `*` in CORS, no payment method, or SQLite. If it does not start, the Render log says which setting to fix.
4. After deploy, open `https://<your-service>.onrender.com/api/health`. It should say `ok` and the payment mode.

The free plan sleeps when idle, so the first request after a pause takes about a minute. The site shows a "waking up" note.

### Razorpay webhook (so paid bookings are never lost)

In the Razorpay dashboard (Test Mode) > Settings > Webhooks, add `https://<your-service>.onrender.com/api/payments/webhook`, the same secret as `RAZORPAY_WEBHOOK_SECRET`, and the events `payment.captured` and `order.paid`.

## 3. Vercel: the website

1. Add New > Project, import this repository, and choose **Import single project** with root directory `frontend`.
2. Environment variable: `VITE_API_BASE` = your Render address, for example `https://sessio-api.onrender.com`.
3. Deploy, then copy the Vercel address into `CORS_ORIGINS` on Render (exact address, `https://`, no trailing slash) and redeploy the API.

The site's security headers are in `frontend/vercel.json`. They allow the API on `*.onrender.com`; if you use another host or a custom domain, add it to `connect-src` there.

## Check it

Sign up, create an expert page, add a service and hours, then book it from a second account in a private window.
