-- Tracks consumption of referral bonus scans (one row per consumed scan)
--
-- Spec A (flat one-time credit): consumption is LIFETIME, never resets.
-- The counter only increases.
--
-- Spec B (recurring monthly bonus): add a reward_month column and filter by
-- it; consumption rows older than the current month can be ignored or the
-- consumed_at month can be compared to the reward_month of each bonus grant.
--
-- Reasoning:
--   Each row = one bonus scan used.  Counting rows gives total_consumed.
--   bonus_remaining = total_earned - total_consumed.
--   Effective cap     = base_daily_cap + bonus_remaining.
--   This avoids a dedicated counter column that would need reset logic.

create table if not exists public.bonus_scan_consumptions (
  id          uuid primary key default gen_random_uuid(),
  user_id     uuid not null references auth.users(id) on delete cascade,
  scan_id     uuid,
  consumed_at timestamptz not null default now()
);

create index if not exists idx_bonus_consumptions_user
  on public.bonus_scan_consumptions (user_id);

-- RLS: service-role only (backend uses service key)
alter table public.bonus_scan_consumptions enable row level security;

create policy "Service role full access to bonus_scan_consumptions"
  on public.bonus_scan_consumptions for all using (true) with check (true);
