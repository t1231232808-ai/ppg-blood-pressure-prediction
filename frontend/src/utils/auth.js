export function getToken() {
  return localStorage.getItem('bp_token') || localStorage.getItem('token')
}

export function getStoredUser() {
  const raw = localStorage.getItem('bp_user') || localStorage.getItem('user')
  if (!raw) return null
  try {
    return JSON.parse(raw)
  } catch {
    return null
  }
}

export function setAuth(token, user) {
  localStorage.setItem('bp_token', token)
  localStorage.setItem('bp_user', JSON.stringify(user))
  localStorage.removeItem('token')
  localStorage.removeItem('user')
}

export function setUser(user) {
  localStorage.setItem('bp_user', JSON.stringify(user))
  localStorage.removeItem('user')
}

export function clearAuth() {
  localStorage.removeItem('bp_token')
  localStorage.removeItem('bp_user')
  localStorage.removeItem('token')
  localStorage.removeItem('user')
}

export function isAdmin() {
  return getStoredUser()?.role === 'admin'
}
