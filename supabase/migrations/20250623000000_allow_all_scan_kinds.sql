-- Allow all active scan kinds in public.scans.kind
alter table public.scans
  drop constraint if exists scans_kind_check,
  add constraint scans_kind_check
    check (kind in ('message', 'screenshot', 'url', 'upi', 'qr', 'file'));
