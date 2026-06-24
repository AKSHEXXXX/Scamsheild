-- Relax the scans.kind check constraint to accept all scan types.
-- The old constraint only allowed 'message' and 'screenshot', causing 23514 errors
-- on URL, UPI, QR, and file scans.

alter table public.scans
  drop constraint if exists scans_kind_check;

alter table public.scans
  add constraint scans_kind_check
  check (kind in (
    'message', 'screenshot', 'text', 'url', 'upi', 'qr', 'file', 'audio'
  ));
