'use client'
import { useEffect, useState, createContext, useContext } from 'react'
import { useRouter, usePathname } from 'next/navigation'
import { supabase } from '@/lib/supabase'
import { adminApi, setToken } from '@/lib/api'
import type { UserInfo } from '@/lib/rbac'
import './globals.css'

type AuthCtx = { user: UserInfo | null; loading: boolean }
const AuthContext = createContext<AuthCtx>({ user: null, loading: true })
export const useAuth = () => useContext(AuthContext)

const PUBLIC_PATHS = ['/login']

export default function RootLayout({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<UserInfo | null>(null)
  const [loading, setLoading] = useState(true)
  const router = useRouter()
  const path = usePathname()

  useEffect(() => {
    supabase.auth.getSession().then(async ({ data: { session } }) => {
      if (!session) {
        if (!PUBLIC_PATHS.includes(path)) router.push('/login')
        setLoading(false)
        return
      }
      setToken(session.access_token)
      try {
        const me = await adminApi.me()
        setUser(me)
      } catch {
        if (!PUBLIC_PATHS.includes(path)) router.push('/login')
      }
      setLoading(false)
    })

    const { data: listener } = supabase.auth.onAuthStateChange((_event, session) => {
      if (session) {
        setToken(session.access_token)
        adminApi.me().then(setUser).catch(() => setUser(null))
      } else {
        setUser(null)
        if (!PUBLIC_PATHS.includes(path)) router.push('/login')
      }
    })
    return () => listener?.subscription.unsubscribe()
  }, [path, router])

  if (loading && !PUBLIC_PATHS.includes(path)) {
    return (
      <html lang="en">
        <body className="flex items-center justify-center min-h-screen">
          <div className="animate-spin h-8 w-8 border-4 border-blue-500 border-t-transparent rounded-full" />
        </body>
      </html>
    )
  }

  return (
    <html lang="en">
      <body>
        <AuthContext.Provider value={{ user, loading }}>
          {children}
        </AuthContext.Provider>
      </body>
    </html>
  )
}
