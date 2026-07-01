-- ScamShield: Referral System + Notifications Schema

-- 1. Referral codes — one per user
create table if not exists public.referrals (
  id          uuid primary key default gen_random_uuid(),
  owner_id    uuid not null references auth.users(id) on delete cascade,
  code        text not null unique,
  created_at  timestamptz not null default now()
);

create index if not exists idx_referrals_owner_id on public.referrals (owner_id);
create index if not exists idx_referrals_code     on public.referrals (code);

-- 2. Referral redemptions — tracks who redeemed which code
create table if not exists public.referral_redemptions (
  id              uuid primary key default gen_random_uuid(),
  referral_id     uuid not null references public.referrals(id) on delete cascade,
  redeemed_by     uuid not null references auth.users(id) on delete cascade,
  redeemed_at     timestamptz not null default now(),
  scans_credited  int not null,
  unique (redeemed_by)
);

create index if not exists idx_redemptions_referral_id on public.referral_redemptions (referral_id);
create index if not exists idx_redemptions_redeemed_by on public.referral_redemptions (redeemed_by);

-- 3. Notifications — lightweight inbox for users
create table if not exists public.notifications (
  id          uuid primary key default gen_random_uuid(),
  user_id     uuid not null references auth.users(id) on delete cascade,
  kind        text not null,
  title       text not null,
  body        text not null,
  read        boolean not null default false,
  created_at  timestamptz not null default now()
);

create index if not exists idx_notifications_user_id on public.notifications (user_id);

-- 4. RLS — service-role only tables (backend uses service key).
-- IMPORTANT: policies must be scoped `to service_role`. A policy with no
-- `to` clause applies to EVERY role (including anon/authenticated), which
-- would let any client holding just the public anon key read/write/delete
-- all referrals, redemptions, and notifications for every user.
alter table public.referrals            enable row level security;
alter table public.referral_redemptions enable row level security;
alter table public.notifications        enable row level security;

create policy "Service role full access to referrals"
  on public.referrals for all
  to service_role
  using (true) with check (true);

create policy "Service role full access to referral_redemptions"
  on public.referral_redemptions for all
  to service_role
  using (true) with check (true);

create policy "Service role full access to notifications"
  on public.notifications for all
  to service_role
  using (true) with check (true);
