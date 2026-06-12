-- ============================================================================
-- ScamShield: Supabase Database Schema
-- Run this in Supabase SQL Editor once to initialize all tables.
-- ============================================================================

-- 1.3 App configuration (single editable row, managed via Supabase Studio)
create table if not exists public.app_config (
  id                    int primary key default 1,
  scan_credit_cap       int  not null default 50,
  ad_frequency          int  not null default 3,
  sensitivity_threshold int  not null default 70,
  config_version        int  not null default 1,
  updated_at            timestamptz not null default now()
);

insert into public.app_config (id) values (1) on conflict do nothing;

-- 1.2 Telemetry / scan log
create table if not exists public.scans (
  id          uuid primary key default gen_random_uuid(),
  user_id     uuid references auth.users(id),
  os          text check (os in ('iOS','Android')),
  risk_score  int,
  verdict     text,
  flagged     boolean default false,
  created_at  timestamptz not null default now()
);

-- 3.2 Blacklist tables with B-tree indexes
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

-- B-tree indexes for fast lookups
create index if not exists idx_vpas_string    on public.blacklisted_vpas    (vpa_string);
create index if not exists idx_numbers_phone  on public.blacklisted_numbers (phone_number);
create index if not exists idx_domains_domain on public.blacklisted_domains (domain);

-- ============================================================================
-- Useful admin queries for telemetry
-- ============================================================================
-- Total scans, active users by platform, flagged threats:
-- select
--   count(*) as total_scans,
--   count(distinct user_id) filter (where os='iOS')     as active_ios_users,
--   count(distinct user_id) filter (where os='Android') as active_android_users,
--   count(*) filter (where flagged)                     as flagged_threats
-- from public.scans;