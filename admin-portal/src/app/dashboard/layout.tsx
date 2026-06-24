'use client'
import { ReactNode } from 'react'
import { useRouter, usePathname } from 'next/navigation'
import { useAuth } from '@/app/layout'
import { hasPermission } from '@/lib/rbac'
import { supabase } from '@/lib/supabase'
import {
  Shield, LayoutDashboard, ScanSearch, Bot, MessageSquare, Settings, LogOut, Menu, X
} from 'lucide-react'
import { useState } from 'react'

const NAV = [
  { href: '/dashboard', label: 'Dashboard', icon: LayoutDashboard, permission: 'dashboard:view' },
  { href: '/scans', label: 'Scans', icon: ScanSearch, permission: 'scans:list' },
  { href: '/agents', label: 'Agents', icon: Bot, permission: 'agents:view' },
  { href: '/feedback', label: 'Feedback', icon: MessageSquare, permission: 'feedback:view' },
  { href: '/settings', label: 'Settings', icon: Settings, permission: 'users:manage' },
]

export default function DashboardLayout({ children }: { children: ReactNode }) {
  const { user, loading } = useAuth()
  const router = useRouter()
  const path = usePathname()
  const [sidebarOpen, setSidebarOpen] = useState(false)

  if (loading) return null

  return (
    <div className="min-h-screen flex">
      {/* Mobile overlay */}
      {sidebarOpen && (
        <div className="fixed inset-0 bg-black/50 z-20 lg:hidden" onClick={() => setSidebarOpen(false)} />
      )}
      {/* Sidebar */}
      <aside className={`fixed lg:static inset-y-0 left-0 z-30 w-64 bg-slate-900 text-white transform transition-transform ${sidebarOpen ? 'translate-x-0' : '-translate-x-full'} lg:translate-x-0 flex flex-col`}>
        <div className="flex items-center gap-2 px-6 py-5 border-b border-slate-700">
          <Shield className="h-6 w-6 text-emerald-400" />
          <span className="font-bold text-lg">ScamShield</span>
        </div>
        <nav className="flex-1 px-3 py-4 space-y-1">
          {NAV.filter(item => hasPermission(user, item.permission)).map(item => {
            const active = path.startsWith(item.href)
            return (
              <a key={item.href} href={item.href}
                className={`flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors ${active ? 'bg-emerald-600 text-white' : 'text-slate-300 hover:bg-slate-800'}`}
                onClick={() => setSidebarOpen(false)}
              >
                <item.icon className="h-5 w-5" />
                {item.label}
              </a>
            )
          })}
        </nav>
        <div className="px-4 py-4 border-t border-slate-700">
          <div className="text-sm text-slate-400 truncate">{user?.email}</div>
          <button onClick={() => { supabase.auth.signOut(); router.push('/login') }}
            className="flex items-center gap-2 mt-2 text-sm text-slate-400 hover:text-white transition-colors"
          >
            <LogOut className="h-4 w-4" /> Sign Out
          </button>
        </div>
      </aside>
      {/* Main */}
      <div className="flex-1 flex flex-col min-w-0">
        <header className="bg-white border-b px-4 py-3 flex items-center gap-3 lg:hidden">
          <button onClick={() => setSidebarOpen(true)} className="p-1 hover:bg-gray-100 rounded">
            <Menu className="h-6 w-6" />
          </button>
          <Shield className="h-5 w-5 text-emerald-600" />
          <span className="font-semibold">ScamShield Admin</span>
        </header>
        <main className="flex-1 p-4 lg:p-6 overflow-auto">
          {children}
        </main>
      </div>
    </div>
  )
}
