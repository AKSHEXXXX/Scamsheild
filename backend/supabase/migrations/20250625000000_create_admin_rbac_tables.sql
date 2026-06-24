CREATE TABLE IF NOT EXISTS public.admin_users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL DEFAULT '',
    avatar_url TEXT DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_login_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS public.roles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT UNIQUE NOT NULL,
    description TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS public.permissions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    resource TEXT NOT NULL,
    action TEXT NOT NULL,
    description TEXT DEFAULT '',
    UNIQUE(resource, action)
);

CREATE TABLE IF NOT EXISTS public.role_permissions (
    role_id UUID NOT NULL REFERENCES public.roles(id) ON DELETE CASCADE,
    permission_id UUID NOT NULL REFERENCES public.permissions(id) ON DELETE CASCADE,
    PRIMARY KEY (role_id, permission_id)
);

CREATE TABLE IF NOT EXISTS public.user_roles (
    user_id UUID NOT NULL REFERENCES public.admin_users(id) ON DELETE CASCADE,
    role_id UUID NOT NULL REFERENCES public.roles(id) ON DELETE CASCADE,
    PRIMARY KEY (user_id, role_id)
);

CREATE TABLE IF NOT EXISTS public.admin_audit_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES public.admin_users(id),
    email TEXT NOT NULL DEFAULT '',
    action TEXT NOT NULL,
    resource_type TEXT NOT NULL DEFAULT '',
    resource_id TEXT NOT NULL DEFAULT '',
    details JSONB DEFAULT '{}' CHECK (jsonb_typeof(details) = 'object' AND pg_column_size(details) <= 4096),
    ip_address TEXT DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.daily_metrics (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    date DATE UNIQUE NOT NULL,
    total_scans INT NOT NULL DEFAULT 0,
    scam_scans INT NOT NULL DEFAULT 0,
    safe_scans INT NOT NULL DEFAULT 0,
    high_risk_scans INT NOT NULL DEFAULT 0,
    suspicious_scans INT NOT NULL DEFAULT 0,
    low_risk_scans INT NOT NULL DEFAULT 0,
    avg_score NUMERIC(5,2) DEFAULT 0,
    unique_users INT NOT NULL DEFAULT 0,
    by_channel JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_admin_audit_log_created_at ON admin_audit_log(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_admin_audit_log_user_id ON admin_audit_log(user_id);
CREATE INDEX IF NOT EXISTS idx_admin_audit_log_action ON admin_audit_log(action);
CREATE INDEX IF NOT EXISTS idx_daily_metrics_date ON daily_metrics(date DESC);

-- Seed permissions
INSERT INTO public.permissions (resource, action, description) VALUES
    ('dashboard', 'view', 'View analytics dashboard'),
    ('scans', 'list', 'List scan records'),
    ('scans', 'view_detail', 'View full scan details'),
    ('agents', 'view', 'View agent status and health'),
    ('agents', 'reset', 'Reset quarantined agents'),
    ('feedback', 'view', 'View user feedback entries'),
    ('users', 'manage', 'Manage admin users and roles')
ON CONFLICT (resource, action) DO NOTHING;

-- Seed roles
INSERT INTO public.roles (name, description) VALUES
    ('ADMIN', 'Full access to all admin features — assign sparingly'),
    ('EXEC', 'Read-only access to dashboards, scans, and feedback'),
    ('OPERATOR', 'Read access + can reset quarantined agents')
ON CONFLICT (name) DO NOTHING;

-- ADMIN gets all permissions
INSERT INTO public.role_permissions (role_id, permission_id)
SELECT r.id, p.id
FROM public.roles r, public.permissions p
WHERE r.name = 'ADMIN'
ON CONFLICT DO NOTHING;

-- EXEC gets read-only permissions (dashboard + scans + feedback + agents view)
INSERT INTO public.role_permissions (role_id, permission_id)
SELECT r.id, p.id
FROM public.roles r, public.permissions p
WHERE r.name = 'EXEC'
  AND ((p.resource = 'dashboard' AND p.action = 'view')
    OR (p.resource = 'scans' AND p.action IN ('list', 'view_detail'))
    OR (p.resource = 'feedback' AND p.action = 'view')
    OR (p.resource = 'agents' AND p.action = 'view'))
ON CONFLICT DO NOTHING;

-- OPERATOR gets EXEC's perms + agents:reset
INSERT INTO public.role_permissions (role_id, permission_id)
SELECT r.id, p.id
FROM public.roles r, public.permissions p
WHERE r.name = 'OPERATOR'
  AND ((p.resource = 'dashboard' AND p.action = 'view')
    OR (p.resource = 'scans' AND p.action IN ('list', 'view_detail'))
    OR (p.resource = 'feedback' AND p.action = 'view')
    OR (p.resource = 'agents' AND p.action IN ('view', 'reset')))
ON CONFLICT DO NOTHING;
