'use client'
import { useEffect, useState } from 'react'
import { adminApi } from '@/lib/api'
import { hasPermission } from '@/lib/rbac'
import { useAuth } from '@/app/layout'
import { useRouter } from 'next/navigation'
import { Shield, ShieldAlert, ShieldCheck, Users } from 'lucide-react'

type Summary = {
  total_scans_today: number
  scam_scans_today: number
  safe_scans_today: number
  high_risk_scans_today: number
  suspicious_scans_today: number
  low_risk_scans_today: number
  unique_active_users_today: number
  avg_score_today?: number
}

export default function DashboardPage() {
  const { user } = useAuth()
  const router = useRouter()
  const [data, setData] = useState<Summary | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!user || !hasPermission(user, 'dashboard:view')) { router.push('/login'); return }
    adminApi.summary().then(setData).finally(() => setLoading(false))
  }, [user, router])

  if (loading) return <div className="animate-pulse space-y-6">{['h-8 w-48', 'h-32', 'h-48'].map((c, i) => <div key={i} className={`${c} bg-gray-200 rounded-lg`} />)}</div>

  const cards = [
    { label: 'Total Scans', value: data?.total_scans_today ?? 0, icon: Shield, color: 'blue' },
    { label: 'High Risk', value: data?.high_risk_scans_today ?? 0, icon: ShieldAlert, color: 'red' },
    { label: 'Suspicious', value: data?.suspicious_scans_today ?? 0, icon: ShieldAlert, color: 'amber' },
    { label: 'Safe', value: data?.safe_scans_today ?? 0, icon: ShieldCheck, color: 'green' },
    { label: 'Active Users', value: data?.unique_active_users_today ?? 0, icon: Users, color: 'purple' },
  ]

  const colorMap: Record<string, string> = {
    blue: 'bg-blue-50 text-blue-700 border-blue-200',
    red: 'bg-red-50 text-red-700 border-red-200',
    amber: 'bg-amber-50 text-amber-700 border-amber-200',
    green: 'bg-green-50 text-green-700 border-green-200',
    purple: 'bg-purple-50 text-purple-700 border-purple-200',
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Dashboard</h1>
      <p className="text-gray-500 text-sm">Today&apos;s scan activity overview</p>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5 gap-4">
        {cards.map(c => (
          <div key={c.label} className={`rounded-xl border p-4 ${colorMap[c.color]}`}>
            <div className="flex items-center justify-between">
              <span className="text-sm font-medium opacity-80">{c.label}</span>
              <c.icon className="h-5 w-5 opacity-60" />
            </div>
            <p className="text-3xl font-bold mt-2">{c.value.toLocaleString()}</p>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Verdict breakdown */}
        <div className="bg-white rounded-xl border p-6">
          <h2 className="font-semibold mb-4">Today by Verdict</h2>
          <div className="space-y-3">
            {[
              { label: 'High Risk', value: data?.high_risk_scans_today ?? 0, color: 'bg-red-500' },
              { label: 'Suspicious', value: data?.suspicious_scans_today ?? 0, color: 'bg-amber-500' },
              { label: 'Low Risk', value: data?.low_risk_scans_today ?? 0, color: 'bg-green-500' },
            ].map(item => {
              const total = data?.total_scans_today || 1
              const pct = total > 0 ? Math.round((item.value / total) * 100) : 0
              return (
                <div key={item.label}>
                  <div className="flex justify-between text-sm mb-1">
                    <span>{item.label}</span>
                    <span className="font-medium">{item.value.toLocaleString()} ({pct}%)</span>
                  </div>
                  <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
                    <div className={`h-full rounded-full ${item.color} transition-all`} style={{ width: `${pct}%` }} />
                  </div>
                </div>
              )
            })}
          </div>
        </div>
        {/* Scam vs Safe */}
        <div className="bg-white rounded-xl border p-6">
          <h2 className="font-semibold mb-4">Scam vs Safe Today</h2>
          <div className="flex items-center justify-center h-40 gap-8">
            <div className="text-center">
              <div className="text-4xl font-bold text-red-600">{data?.scam_scans_today ?? 0}</div>
              <div className="text-sm text-gray-500 mt-1">Scam</div>
            </div>
            <div className="text-4xl text-gray-300">|</div>
            <div className="text-center">
              <div className="text-4xl font-bold text-green-600">{data?.safe_scans_today ?? 0}</div>
              <div className="text-sm text-gray-500 mt-1">Safe</div>
            </div>
          </div>
          {data && data.total_scans_today > 0 && (
            <p className="text-center text-sm text-gray-400">
              {Math.round((data.scam_scans_today / data.total_scans_today) * 100)}% scam rate
            </p>
          )}
        </div>
      </div>
    </div>
  )
}
