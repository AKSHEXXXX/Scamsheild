-- Feedback table for user-labeled scan results
create table if not exists public.feedback (
  id          uuid primary key default gen_random_uuid(),
  scan_id     text not null,
  user_id     text not null,
  label       text not null check (label in ('scam','legit','unsure')),
  reason      text,
  created_at  timestamptz not null default now()
);

create index if not exists idx_feedback_scan_id  on public.feedback (scan_id);
create index if not exists idx_feedback_user_id  on public.feedback (user_id);
