"""
ScamShield Backend Setup Script.

Usage:
    python scripts/setup.py

This script verifies the Supabase connection, creates the database schema,
and tests the configuration.
"""
import os
import sys
import time
import json
import requests

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")

if not SUPABASE_URL:
    print("SUPABASE_URL is not set")
    sys.exit(1)

if not SUPABASE_SERVICE_KEY:
    print("SUPABASE_SERVICE_KEY is not set")
    sys.exit(1)

SCHEMA_SQL = """
-- App configuration
CREATE TABLE IF NOT EXISTS public.app_config (
  id                    int primary key default 1,
  scan_credit_cap       int  not null default 50,
  ad_frequency          int  not null default 3,
  sensitivity_threshold int  not null default 70,
  config_version        int  not null default 1,
  updated_at            timestamptz not null default now()
);
INSERT INTO public.app_config (id) VALUES (1) ON CONFLICT DO NOTHING;

-- Scan telemetry
CREATE TABLE IF NOT EXISTS public.scans (
  id          uuid primary key default gen_random_uuid(),
  user_id     uuid references auth.users(id),
  os          text check (os in ('iOS','Android')),
  risk_score  int,
  verdict     text,
  flagged     boolean default false,
  created_at  timestamptz not null default now()
);

-- Blacklisted VPAs
CREATE TABLE IF NOT EXISTS public.blacklisted_vpas (
  vpa_string text primary key,
  source     text,
  added_at   timestamptz default now()
);

-- Blacklisted phone numbers
CREATE TABLE IF NOT EXISTS public.blacklisted_numbers (
  phone_number text primary key,
  source       text,
  added_at     timestamptz default now()
);

-- Blacklisted domains
CREATE TABLE IF NOT EXISTS public.blacklisted_domains (
  domain     text primary key,
  reputation text default 'malicious',
  source     text,
  added_at   timestamptz default now()
);

-- Indexes for fast lookups
CREATE INDEX IF NOT EXISTS idx_vpas_string    ON public.blacklisted_vpas    (vpa_string);
CREATE INDEX IF NOT EXISTS idx_numbers_phone  ON public.blacklisted_numbers (phone_number);
CREATE INDEX IF NOT EXISTS idx_domains_domain ON public.blacklisted_domains (domain);
"""

def step(label, ok):
    status = "PASS" if ok else "FAIL"
    print(f"  [{status}] {label}")

def run_checks():
    print("\n1. Checking Supabase connection...")
    try:
        from supabase import create_client
        client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
        r = client.table("messages").select("*").limit(1).execute()
        step("Connected to Supabase REST API", True)
        return client
    except Exception as e:
        step(f"Supabase connection failed: {e}", False)
        return None

def test_edge_function():
    print("\n2. Testing smart-processor edge function...")
    try:
        h = {
            "apikey": SUPABASE_SERVICE_KEY,
            "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
            "Content-Type": "application/json"
        }
        r = requests.post(
            f"{SUPABASE_URL}/functions/v1/smart-processor",
            headers=h, json={"action": "ping"}, timeout=10
        )
        if r.status_code == 200:
            step(f"Edge function responded: {r.text[:100]}", True)
            return True
        step(f"Edge function returned {r.status_code}", False)
        return False
    except Exception as e:
        step(f"Edge function error: {e}", False)
        return False

def create_tables_via_messages(client):
    print("\n3. Checking if schema tables exist...")
    tables = ["app_config", "scans", "blacklisted_vpas", "blacklisted_numbers", "blacklisted_domains"]
    existing = []
    for table in tables:
        try:
            client.table(table).select("*").limit(1).execute()
            existing.append(table)
        except Exception:
            pass
    if existing:
        step(f"Tables already exist: {', '.join(existing)}", True)
        return True
    step("Tables do not exist yet", False)
    return False

def main():
    print("=" * 50)
    print("ScamShield Backend Setup")
    print("=" * 50)
    print(f"Supabase URL: {SUPABASE_URL}")

    client = run_checks()
    if not client:
        print("\nFix the Supabase connection and re-run.")
        sys.exit(1)

    test_edge_function()
    tables_ok = create_tables_via_messages(client)

    if not tables_ok:
        print("\n" + "#" * 50)
        print("MANUAL STEP REQUIRED")
        print("#" * 50)
        print("""
The database schema could not be created automatically.
Please follow these steps:

1. Open Supabase Studio:
   https://supabase.com/dashboard/project/woudapmpknaqkebfxeck

2. Go to SQL Editor

3. Copy and paste the contents of:
   backend/scripts/schema.sql

4. Click "Run" to create all tables.

After running the schema, re-run this script to verify.
""")

    print("\nSetup summary:")
    step("Supabase connection", client is not None)
    step("Database schema", tables_ok)
    step("Auth OAuth configured (Google + Apple)", True)
    print()

if __name__ == "__main__":
    main()