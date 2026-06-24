'use client'
import { useEffect, useState } from 'react'
import { useParams, useRouter } from 'next/navigation'
import { adminApi } from '@/lib/api'
import { hasPermission } from '@/lib/rbac'
import { useAuth } from '@/app/layout'
import { ArrowLeft, ShieldAlert, ShieldCheck, AlertTriangle } from 'lucide-react'

type AgentDecision = { agent_id: number; name: string; score: number; verdict: string; signals: string[] }
type Feedback = { user_id: string; label: string; reason: string; created_at: string }

export default function ScanDetailPage() {
  const { user } = useAuth()
  const router = useRouter()
  const params = useParams()
  const [data, setData] = useState<any>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!user || !hasPermission(user, 'scans:view_detail')) { router.push('/login'); return }
    if (params.scan_id) {
      adminApi.scanDetail(params.scan_id as string).then(setData).finally(() => setLoading(false))
    }
  }, [user, router, params.scan_id])

  if (loading) return <div className="animate-pulse space-y-4"><div className="h-8 w-48 bg-gray-200 rounded" /><div className="h-64 bg-gray-200 rounded" /></div>
  if (!data) return <div className="text-gray-500">Scan not found</div>

  const verdictIcon = data.verdict === 'high_risk' ? ShieldAlert :
    data.verdict === 'suspicious' ? AlertTriangle : ShieldCheck
  const verdictColor = data.verdict === 'high_risk' ? 'text-red-600' :
    data.verdict === 'suspicious' ? 'text-amber-600' : 'text-green-600'

  return (
    <div className="space-y-6 max-w-4xl">
      <button onClick={() => router.push('/scans')} className="flex items-center gap-1 text-sm text-gray-500 hover:text-gray-700">
        <ArrowLeft className="h-4 w-4" /> Back to Scans
      </button>

      <div className="flex items-center gap-3">
        {verdictIcon && <verdictIcon className={`h-8 w-8 ${verdictColor}`} />}
        <div>
          <h1 className="text-2xl font-bold">Scan Detail</h1>
          <p className="text-sm text-gray-500 font-mono">{data.scan_id}</p>
        </div>
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {[
          { label: 'Channel', value: data.channel },
          { label: 'Verdict', value: data.verdict, color: verdictColor },
          { label: 'Score', value: data.score },
          { label: 'Flags', value: data.flagged ? '⚠ Flagged' : 'Normal' },
          { label: 'Warning Count', value: data.warning_count },
          { label: 'Time', value: data.timestamp ? new Date(data.timestamp).toLocaleString() : '-' },
          { label: 'Top Signal', value: data.top_signal || 'N/A' },
        ].map(f => (
          <div key={f.label} className="bg-white rounded-xl border p-4">
            <div className="text-xs text-gray-500 mb-1">{f.label}</div>
            <div className={`font-semibold ${f.color || ''}`}>{String(f.value)}</div>
          </div>
        ))}
      </div>

      {data.input_preview && (
        <div className="bg-white rounded-xl border p-4">
          <h2 className="font-semibold mb-2">Input Preview</h2>
          <p className="text-sm text-gray-600 break-words font-mono bg-gray-50 p-3 rounded">{data.input_preview}</p>
        </div>
      )}

      {data.agent_decisions && data.agent_decisions.length > 0 && (
        <div className="bg-white rounded-xl border">
          <div className="px-4 py-3 border-b font-semibold">Agent Decisions</div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-gray-50">
                <tr>
                  <th className="text-left px-4 py-2">Agent</th>
                  <th className="text-left px-4 py-2">Name</th>
                  <th className="text-right px-4 py-2">Score</th>
                  <th className="text-left px-4 py-2">Verdict</th>
                  <th className="text-left px-4 py-2">Signals</th>
                </tr>
              </thead>
              <tbody className="divide-y">
                {data.agent_decisions.map((a: AgentDecision) => (
                  <tr key={a.agent_id}>
                    <td className="px-4 py-2 font-mono">#{a.agent_id}</td>
                    <td className="px-4 py-2">{a.name}</td>
                    <td className="px-4 py-2 text-right font-mono">{a.score.toFixed(2)}</td>
                    <td className="px-4 py-2">
                      <span className={`inline-block px-2 py-0.5 rounded text-xs font-medium ${VERDICT_CLASSES[a.verdict] || ''}`}>{a.verdict}</span>
                    </td>
                    <td className="px-4 py-2 text-gray-500 text-xs">
                      {a.signals?.join(', ') || '-'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {data.feedback && data.feedback.length > 0 && (
        <div className="bg-white rounded-xl border p-4">
          <h2 className="font-semibold mb-3">User Feedback</h2>
          <div className="space-y-2">
            {data.feedback.map((fb: Feedback, i: number) => (
              <div key={i} className="flex items-start gap-3 text-sm bg-gray-50 rounded-lg p-3">
                <span className={`px-2 py-0.5 rounded text-xs font-medium ${fb.label === 'scam' ? 'bg-red-100 text-red-700' : fb.label === 'legit' ? 'bg-green-100 text-green-700' : 'bg-gray-200'}`}>
                  {fb.label}
                </span>
                <div>
                  <p className="text-gray-600">{fb.reason || 'No reason given'}</p>
                  <p className="text-gray-400 text-xs mt-1">{fb.created_at ? new Date(fb.created_at).toLocaleString() : ''}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

const VERDICT_CLASSES: Record<string, string> = {
  high_risk: 'bg-red-100 text-red-700',
  suspicious: 'bg-amber-100 text-amber-700',
  low_risk: 'bg-green-100 text-green-700',
  error: 'bg-gray-100 text-gray-500',
}
