# Railway Environment Variables — ScamShield Backend

## Required Variables

| Variable              | Value                                           |
|-----------------------|-------------------------------------------------|
| SUPABASE_URL          | https://pmwdoxemzdupicidzmze.supabase.co        |
| SUPABASE_SERVICE_KEY  | <service_role key from Supabase dashboard>      |
| MODEL_DIR             | /app/models  (or wherever pkl files are served) |

## NOT Required
- SUPABASE_JWT_SECRET — not used by this backend. Remove it from Railway to avoid confusion.

## Verification
After setting the above, Railway deploy logs should show:
  SUPABASE_URL set: True
  SUPABASE_SERVICE_KEY set: True
  SUPABASE_URL project ref: pmwdoxemzdupicidzmze

Any 401 after this will log: Token validation failed — alg=... iss=... exc=...
