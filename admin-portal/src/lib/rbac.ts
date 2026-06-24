export type UserInfo = {
  email: string
  name: string
  roles: string[]
  permissions: string[]
}

export function hasPermission(user: UserInfo | null, permission: string): boolean {
  if (!user) return false
  return user.permissions.includes(permission)
}

export function hasRole(user: UserInfo | null, role: string): boolean {
  if (!user) return false
  return user.roles.includes(role)
}
