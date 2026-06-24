'use client'
import { useEffect, useState } from 'react'
import { adminApi } from '@/lib/api'
import { hasPermission } from '@/lib/rbac'
import { useAuth } from '@/app/layout'
import { useRouter } from 'next/navigation'
import { RotateCw, AlertCircle, CheckCircle, XCircle } from 'lucide-react'

type Agent = {
  id: number
  name: string
  status: string
  status_detail: string
  health: {
    consecutive_errors?: number
    total_errors?: number
    disabled?: boolean
    cooldown_remaining_s?: number
  }
}

export default function AgentsPage() {
  const { user } = useAuth()
  const router = useRouter()
  const [agents, setAgents] = useState<Agent[]>([])
  const [loading, setLoading] = useState(true)
  const [resetting, setResetting] = useState<string | null>(null)

  const canReset = hasPermission(user, 'agents:reset')

  const fetchAgents = () => {
    adminApi.agents().then(res => setAgents(res.agents)).finally(() => setLoading(false))
  }

  useEffect(() => {
    if (!user || !hasPermission(user, 'agents:view')) { router.push('/login'); return }
    fetchAgents()
  }, [user, router])

  const handleReset = async (agentId: string) => {
    setResetting(agentId)
    try {
      await adminApi.resetAgent(agentId)
      fetchAgents()
    } catch (e: any) {
      alert(e.message)
    }
    setResetting(null)
  }

  if (loading) return <div className="animate-pulse space-y-3">{[1,2,3,4,5].map(i => <div key={i} className="h-16 bg-gray-200 rounded-lg" />)}</div>

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold">Agent Health</h1>

      <div className="space-y-2">
        {agents.map(agent => {
          const h = agent.health || {}
          const disabled = h.disabled
          return (
            <div key={agent.id} className={`bg-white rounded-xl border p-4 flex items-center justify-between ${disabled ? 'border-red-300 bg-red-50' : ''}`}>
              <div className="flex items-center gap-4">
                <div>
                  {disabled ? <XCircle className="h-8 w-8 text-red-500" /> :
                   agent.status === 'READY' ? <CheckCircle className="h-8 w-8 text-green-500" /> :
                   <AlertCircle className="h-8 w-8 text-amber-500" />}
                </div>
                <div>
                  <div className="font-semibold">#{agent.id} {agent.name}</div>
                  <div className="text-sm text-gray-500">
                    Status: <span className={`font-medium ${disabled ? 'text-red-600' : agent.status === 'READY' ? 'text-green-600' : 'text-amber-600'}`}>
                      {disabled ? 'DISABLED' : agent.status}
                    </span>
                    {agent.status_detail && <span className="ml-2">| {agent.status_detail}</span>}
                  </div>
                  {h.total_errors !== undefined && h.total_errors > 0 && (
                    <div className="text-xs text-gray-400 mt-1">
                      {h.total_errors} error(s) total
                      {h.cooldown_remaining_s ? ` | cooldown ${h.cooldown_remaining_s}s remaining` : ''}
                    </div>
                  )}
                </div>
              </div>
              {canReset && (
                <button onClick={() => handleReset(`agent${agent.id}`)}
                  disabled={resetting === `agent${agent.id}`}
                  className="flex items-center gap-1 px-3 py-1.5 text-sm border rounded-lg hover:bg-gray-50 disabled:opacity-50"
                >
                  <RotateCw className={`h-4 w-4 ${resetting === `agent${agent.id}` ? 'animate-spin' : ''}`} />
                  Reset
                </button>
              )}
            </div>
          )
        })}
        {agents.length === 0 && <div className="text-center text-gray-400 py-8">No agents found</div>}
      </div>
    </div>
  )
}
