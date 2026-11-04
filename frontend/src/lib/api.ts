import type { DashboardData, ReportData, Session, Transaction, TransactionForm } from './types'

let csrfToken: string | null = null
export function setCsrfToken(token: string | null) { csrfToken = token }

export class ApiError extends Error {
  constructor(message: string, public status: number) { super(message) }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  let response: Response
  try {
    response = await fetch(`/api${path}`, {
      credentials: 'same-origin',
      ...init,
      headers: {
        ...(init.body ? { 'Content-Type': 'application/json' } : {}),
        ...(init.method && !['GET', 'HEAD'].includes(init.method.toUpperCase()) && csrfToken
          ? { 'X-CSRF-Token': csrfToken } : {}),
        ...init.headers,
      },
    })
  } catch {
    throw new ApiError('Unable to connect to GharKhata. Please check your connection.', 0)
  }
  if (!response.ok) {
    const json = await response.json().catch(() => ({}))
    const message = typeof json.detail === 'string' ? json.detail
      : Array.isArray(json.detail) ? json.detail.map((item: { msg?: string }) => item.msg || 'Invalid input').join(' · ')
        : 'Something went wrong. Please try again.'
    throw new ApiError(message, response.status)
  }
  if (response.status === 204) return undefined as T
  return response.json() as Promise<T>
}

export const api = {
  me: () => request<Session>('/auth/me'),
  async login(email: string, password: string) {
    const session = await request<Session>('/auth/login', {
      method: 'POST', body: JSON.stringify({ email, password }),
    })
    setCsrfToken(session.csrf_token)
    return session
  },
  async logout() {
    await request<void>('/auth/logout', { method: 'POST' })
    setCsrfToken(null)
  },
  dashboard: (month: string) => request<DashboardData>(`/dashboard?month=${encodeURIComponent(month)}`),
  transactions: (filters: { month?: string; type?: string; category?: string; search?: string } = {}) => {
    const search = new URLSearchParams()
    Object.entries(filters).forEach(([key, value]) => { if (value) search.set(key, value) })
    return request<Transaction[]>(`/transactions?${search.toString()}`)
  },
  add: (transaction: TransactionForm) => request<Transaction>('/transactions', { method: 'POST', body: JSON.stringify(transaction) }),
  edit: (id: string, transaction: TransactionForm) => request<Transaction>(`/transactions/${id}`, { method: 'PUT', body: JSON.stringify(transaction) }),
  delete: (id: string) => request<void>(`/transactions/${id}`, { method: 'DELETE' }),
  report: (start: string, end: string) => request<ReportData>(`/reports?${reportQuery(start, end)}`),
  reportDownloadUrl: (start: string, end: string) => `/api/reports/export?${reportQuery(start, end)}`,
}
function reportQuery(start: string, end: string) {
  return new URLSearchParams({ start_date: start, end_date: end }).toString()
}
