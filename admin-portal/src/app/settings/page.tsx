'use client'
import { useAuth } from '@/app/layout'
import { hasPermission } from '@/lib/rbac'
import { useRouter } from 'next/navigation'
import { useEffect } from 'react'
import { Shield, User, Key, ListChecks } from 'lucide-react'

export default function SettingsPage() {
  const { user } = useAuth()
  const router = useRouter()

  useEffect(() => {
    if (!user || !hasPermission(user, 'users:manage')) { router.push('/login'); return }
  }, [user, router])

  if (!user) return null

  return (
    <div className="space-y-6 max-w-2xl">
      <h1 className="text-2xl font-bold">Settings</h1>

      <div className="bg-white rounded-xl border p-6 space-y-6">
        <div className="flex items-center gap-3">
          <User className="h-10 w-10 p-2 bg-blue-100 text-blue-700 rounded-lg" />
          <div>
            <div className="font-semibold">{user.name}</div>
            <div className="text-sm text-gray-500">{user.email}</div>
          </div>
        </div>

        <div>
          <h2 className="font-semibold flex items-center gap-2 mb-3">
            <Key className="h-4 w-4" /> Roles
          </h2>
          <div className="flex flex-wrap gap-2">
            {user.roles.map(r => (
              <span key={r} className="px-3 py-1 bg-slate-100 text-slate-700 rounded-full text-sm font-medium">
                {r}
              </span>
            ))}
          </div>
        </div>

        <div>
          <h2 className="font-semibold flex items-center gap-2 mb-3">
            <ListChecks className="h-4 w-4" /> Permissions
          </h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
            {user.permissions.map(p => (
              <div key={p} className="flex items-center gap-2 text-sm text-gray-600">
                <Shield className="h-3 w-3 text-emerald-500 flex-shrink-0" />
                {p}
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
