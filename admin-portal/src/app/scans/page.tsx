'use client'
import { useEffect, useState, useCallback } from 'react'
import { adminApi } from '@/lib/api'
import { hasPermission } from '@/lib/rbac'
import { useAuth } from '@/app/layout'
import { useRouter } from 'next/navigation'
import { Search, Filter, ChevronLeft, ChevronRight } from 'lucide-react'

type ScanRow = {
  scan_id: string
  timestamp: string
  channel: string
  verdict: string
  score: number
  warning_count: number
  flagged: boolean
  input_preview: string
}

const VERDICT_COLORS: Record<string, string> = {
  high_risk: 'bg-red-100 text-red-700',
  suspicious: 'bg-amber-100 text-amber-700',
  low_risk: 'bg-green-100 text-green-700',
}

export default function ScansPage() {
  const { user } = useAuth()
  const router = useRouter()
  const [items, setItems] = useState<ScanRow[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [pageSize] = useState(25)
  const [filterVerdict, setFilterVerdict] = useState('')
  const [filterChannel, setFilterChannel] = useState('')
  const [loading, setLoading] = useState(true)

  const fetchScans = useCallback(async () => {
    setLoading(true)
    const params: Record<string, string> = { page: String(page), page_size: String(pageSize) }
    if (filterVerdict) params.verdict = filterVerdict
    if (filterChannel) params.channel = filterChannel
    const res = await adminApi.scans(params)
    setItems(res.items)
    setTotal(res.total)
    setLoading(false)
  }, [page, pageSize, filterVerdict, filterChannel])

  useEffect(() => {
    if (!user || !hasPermission(user, 'scans:list')) { router.push('/login'); return }
    fetchScans()
  }, [user, router, fetchScans])

  const totalPages = Math.ceil(total / pageSize)

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold">Scans Explorer</h1>

      <div className="flex flex-wrap gap-3 items-center">
        <select value={filterVerdict} onChange={e => { setFilterVerdict(e.target.value); setPage(1) }}
          className="border rounded-lg px-3 py-2 text-sm bg-white">
          <option value="">All Verdicts</option>
          <option value="high_risk">High Risk</option>
          <option value="suspicious">Suspicious</option>
          <option value="low_risk">Low Risk</option>
        </select>
        <select value={filterChannel} onChange={e => { setFilterChannel(e.target.value); setPage(1) }}
          className="border rounded-lg px-3 py-2 text-sm bg-white">
          <option value="">All Channels</option>
          <option value="text">Text</option>
          <option value="url">URL</option>
          <option value="upi">UPI</option>
          <option value="qr">QR</option>
          <option value="image">Image</option>
          <option value="file">File</option>
          <option value="audio">Audio</option>
        </select>
        <span className="text-sm text-gray-500 ml-auto">{total} total scans</span>
      </div>

      <div className="bg-white rounded-xl border overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 border-b">
              <tr>
                <th className="text-left px-4 py-3 font-medium">Scan ID</th>
                <th className="text-left px-4 py-3 font-medium">Time</th>
                <th className="text-left px-4 py-3 font-medium">Channel</th>
                <th className="text-left px-4 py-3 font-medium">Verdict</th>
                <th className="text-right px-4 py-3 font-medium">Score</th>
                <th className="text-left px-4 py-3 font-medium">Preview</th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {items.map(item => (
                <tr key={item.scan_id} className="hover:bg-gray-50 cursor-pointer"
                  onClick={() => router.push(`/scans/${item.scan_id}`)}>
                  <td className="px-4 py-3 font-mono text-xs text-gray-500">{item.scan_id.slice(0, 8)}...</td>
                  <td className="px-4 py-3 text-gray-500 whitespace-nowrap">
                    {item.timestamp ? new Date(item.timestamp).toLocaleString() : '-'}
                  </td>
                  <td className="px-4 py-3 capitalize">{item.channel}</td>
                  <td className="px-4 py-3">
                    <span className={`inline-block px-2 py-0.5 rounded-full text-xs font-medium ${VERDICT_COLORS[item.verdict] || 'bg-gray-100'}`}>
                      {item.verdict}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-right font-mono">{item.score}</td>
                  <td className="px-4 py-3 text-gray-500 max-w-xs truncate">{item.input_preview}</td>
                </tr>
              ))}
              {items.length === 0 && (
                <tr><td colSpan={6} className="px-4 py-8 text-center text-gray-400">No scans found</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {totalPages > 1 && (
        <div className="flex items-center justify-center gap-2">
          <button disabled={page <= 1} onClick={() => setPage(p => p - 1)}
            className="p-2 rounded-lg border hover:bg-gray-50 disabled:opacity-30">
            <ChevronLeft className="h-4 w-4" />
          </button>
          <span className="text-sm text-gray-500">Page {page} of {totalPages}</span>
          <button disabled={page >= totalPages} onClick={() => setPage(p => p + 1)}
            className="p-2 rounded-lg border hover:bg-gray-50 disabled:opacity-30">
            <ChevronRight className="h-4 w-4" />
          </button>
        </div>
      )}
    </div>
  )
}
