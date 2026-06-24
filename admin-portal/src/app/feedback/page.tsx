'use client'
import { useEffect, useState, useCallback } from 'react'
import { adminApi } from '@/lib/api'
import { hasPermission } from '@/lib/rbac'
import { useAuth } from '@/app/layout'
import { useRouter } from 'next/navigation'

type FeedbackRow = {
  scan_id: string
  user_id: string
  channel: string
  label: string
  reason: string
  created_at: string
  model_verdict: string
  model_score: number
  delta: string
}

const DELTA_COLORS: Record<string, string> = {
  agrees: 'bg-green-100 text-green-700',
  possible_fn: 'bg-red-100 text-red-700',
  possible_fp: 'bg-amber-100 text-amber-700',
  disagrees: 'bg-gray-100 text-gray-600',
}
const LABEL_COLORS: Record<string, string> = {
  scam: 'bg-red-100 text-red-700',
  legit: 'bg-green-100 text-green-700',
  unsure: 'bg-gray-100 text-gray-600',
}

export default function FeedbackPage() {
  const { user } = useAuth()
  const router = useRouter()
  const [items, setItems] = useState<FeedbackRow[]>([])
  const [filterLabel, setFilterLabel] = useState('')
  const [loading, setLoading] = useState(true)

  const fetchFeedback = useCallback(async () => {
    setLoading(true)
    const params: Record<string, string> = {}
    if (filterLabel) params.label = filterLabel
    const res = await adminApi.feedback(params)
    setItems(res.items)
    setLoading(false)
  }, [filterLabel])

  useEffect(() => {
    if (!user || !hasPermission(user, 'feedback:view')) { router.push('/login'); return }
    fetchFeedback()
  }, [user, router, fetchFeedback])

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold">Feedback Review</h1>

      <select value={filterLabel} onChange={e => setFilterLabel(e.target.value)}
        className="border rounded-lg px-3 py-2 text-sm bg-white">
        <option value="">All Labels</option>
        <option value="scam">Scam</option>
        <option value="legit">Legit</option>
        <option value="unsure">Unsure</option>
      </select>

      <div className="bg-white rounded-xl border overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 border-b">
              <tr>
                <th className="text-left px-4 py-3 font-medium">Scan ID</th>
                <th className="text-left px-4 py-3 font-medium">User</th>
                <th className="text-left px-4 py-3 font-medium">Channel</th>
                <th className="text-left px-4 py-3 font-medium">User Says</th>
                <th className="text-left px-4 py-3 font-medium">Model</th>
                <th className="text-right px-4 py-3 font-medium">Score</th>
                <th className="text-left px-4 py-3 font-medium">Delta</th>
                <th className="text-left px-4 py-3 font-medium">Reason</th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {items.map((item, i) => (
                <tr key={`${item.scan_id}-${i}`} className="hover:bg-gray-50 cursor-pointer"
                  onClick={() => router.push(`/scans/${item.scan_id}`)}>
                  <td className="px-4 py-3 font-mono text-xs text-gray-500">{item.scan_id.slice(0, 8)}...</td>
                  <td className="px-4 py-3 text-xs text-gray-500">{item.user_id}</td>
                  <td className="px-4 py-3 capitalize">{item.channel}</td>
                  <td className="px-4 py-3">
                    <span className={`inline-block px-2 py-0.5 rounded text-xs font-medium ${LABEL_COLORS[item.label] || ''}`}>{item.label}</span>
                  </td>
                  <td className="px-4 py-3">{item.model_verdict || '-'}</td>
                  <td className="px-4 py-3 text-right font-mono">{item.model_score}</td>
                  <td className="px-4 py-3">
                    <span className={`inline-block px-2 py-0.5 rounded text-xs font-medium ${DELTA_COLORS[item.delta] || ''}`}>{item.delta}</span>
                  </td>
                  <td className="px-4 py-3 text-gray-500 max-w-xs truncate">{item.reason || '-'}</td>
                </tr>
              ))}
              {items.length === 0 && (
                <tr><td colSpan={8} className="px-4 py-8 text-center text-gray-400">No feedback found</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
