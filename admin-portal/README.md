# ScamShield Admin Portal

Internal analytics dashboard for the ScamShield backend.

## Setup

```bash
cp .env.local.example .env.local
# Edit .env.local with your credentials
npm install
npm run dev
```

## Environment Variables

| Variable | Description |
|---|---|
| `NEXT_PUBLIC_BACKEND_BASE_URL` | Backend API base URL (e.g., `https://api.railway.app`) |
| `NEXT_PUBLIC_SUPABASE_URL` | Supabase project URL for auth |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | Supabase anon key (safe for client-side) |
| `NEXT_PUBLIC_ALLOWED_EMAIL_DOMAIN` | Restrict login to `@domain` emails |

## Pages

- `/login` — Company email auth via Supabase
- `/dashboard` — KPI cards + scam/safe breakdown
- `/scans` — Paginated scans explorer with filters
- `/scans/[scan_id]` — Full scan detail + agent decisions + feedback
- `/agents` — Agent health, quarantine status, manual reset
- `/feedback` — User feedback table with delta analysis
- `/settings` — Current user roles & permissions (ADMIN only)

## Deploy

Built for Railway. Set `output: 'standalone'` in next.config.js already.
