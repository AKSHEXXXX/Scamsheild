-- ============================================================================
-- ScamShield: Supabase Database Schema Migration
-- ============================================================================

-- 1. App configuration
create table if not exists public.app_config (
  id                    int primary key default 1,
  scan_credit_cap       int  not null default 50,
  ad_frequency          int  not null default 3,
  sensitivity_threshold int  not null default 70,
  config_version        int  not null default 1,
  updated_at            timestamptz not null default now()
);

insert into public.app_config (id) values (1) on conflict do nothing;

-- 2. Scans / telemetry log
create table if not exists public.scans (
  id              uuid primary key default gen_random_uuid(),
  kind            text not null check (kind in ('message','screenshot')),
  user_id         uuid not null references auth.users(id),
  device_id       text not null default 'unknown',
  os              text not null check (os in ('iOS','Android')),
  input_text      text,
  result_json     jsonb,
  risk_score      integer not null,
  verdict         text not null check (verdict in ('low_risk','suspicious','high_risk')),
  warning_count   integer not null default 0,
  flagged         boolean not null default false,
  ocr_method      text,
  ocr_confidence  double precision,
  created_at      timestamptz not null default now()
);

create index if not exists idx_scans_user_id      on public.scans (user_id);
create index if not exists idx_scans_created_at    on public.scans (created_at desc);
create index if not exists idx_scans_user_created  on public.scans (user_id, created_at desc);

-- 3. Reports
create table if not exists public.reports (
  id          uuid primary key default gen_random_uuid(),
  report_type text check (report_type in ('upi','phone','link','other')),
  value       text not null,
  channel     text check (channel in ('whatsapp','sms','phone_call','email')),
  description text,
  os          text check (os in ('iOS','Android')),
  device_id   text,
  user_id     uuid references auth.users(id),
  created_at  timestamptz not null default now()
);

create index if not exists idx_reports_device_id on public.reports (device_id);
create index if not exists idx_reports_user_id   on public.reports (user_id);

-- 4. Blacklist tables
create table if not exists public.blacklisted_vpas (
  vpa_string text primary key,
  source     text,
  added_at   timestamptz default now()
);

create table if not exists public.blacklisted_numbers (
  phone_number text primary key,
  source       text,
  added_at     timestamptz default now()
);

create table if not exists public.blacklisted_domains (
  domain     text primary key,
  reputation text default 'malicious',
  source     text,
  added_at   timestamptz default now()
);

create index if not exists idx_vpas_string    on public.blacklisted_vpas    (vpa_string);
create index if not exists idx_numbers_phone  on public.blacklisted_numbers (phone_number);
create index if not exists idx_domains_domain on public.blacklisted_domains (domain);

-- 5. Enable Row Level Security
alter table public.app_config enable row level security;
alter table public.scans enable row level security;
alter table public.reports enable row level security;
alter table public.blacklisted_vpas enable row level security;
alter table public.blacklisted_numbers enable row level security;
alter table public.blacklisted_domains enable row level security;

-- 6. RLS Policies
create policy "Service role full access to app_config"
  on public.app_config for all using (true) with check (true);

create policy "scans_owner_select"
  on public.scans for select using (auth.uid() = user_id);

create policy "scans_owner_insert"
  on public.scans for insert with check (auth.uid() = user_id);

create policy "Users can read their own reports"
  on public.reports for select using (auth.uid() = user_id);

create policy "Service role can insert reports"
  on public.reports for insert with check (true);

create policy "Service role full access to blacklisted_vpas"
  on public.blacklisted_vpas for all using (true) with check (true);

create policy "Service role full access to blacklisted_numbers"
  on public.blacklisted_numbers for all using (true) with check (true);

create policy "Service role full access to blacklisted_domains"
  on public.blacklisted_domains for all using (true) with check (true);
