const BASE = process.env.NEXT_PUBLIC_BACKEND_BASE_URL || 'http://localhost:8000'

let _token: string | null = null

export function setToken(token: string) {
  _token = token
}
export function getToken() {
  return _token
}

async function fetchApi(path: string, init?: RequestInit) {
  const headers: Record<string, string> = { 'Content-Type': 'application/json' }
  if (_token) headers['Authorization'] = `Bearer ${_token}`
  const res = await fetch(`${BASE}${path}`, { ...init, headers })
  if (res.status === 401 || res.status === 403) {
    if (typeof window !== 'undefined') {
      window.location.href = '/login'
    }
    throw new Error('Unauthorized')
  }
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new Error(body.detail || `HTTP ${res.status}`)
  }
  return res.json()
}

export const adminApi = {
  me: () => fetchApi('/api/v1/admin/me'),
  summary: () => fetchApi('/api/v1/admin/summary'),
  scans: (params?: Record<string, string>) => {
    const q = params ? '?' + new URLSearchParams(params).toString() : ''
    return fetchApi('/api/v1/admin/scans' + q)
  },
  scanDetail: (id: string) => fetchApi(`/api/v1/admin/scan/${id}`),
  agents: () => fetchApi('/api/v1/admin/agents'),
  resetAgent: (agentId: string) =>
    fetchApi('/api/v1/admin/agents/reset', {
      method: 'POST',
      body: JSON.stringify({ agent_id: agentId }),
    }),
  quarantineEvents: () => fetchApi('/api/v1/admin/quarantine-events'),
  feedback: (params?: Record<string, string>) => {
    const q = params ? '?' + new URLSearchParams(params).toString() : ''
    return fetchApi('/api/v1/admin/feedback' + q)
  },
}
