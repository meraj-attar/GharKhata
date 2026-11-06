import type { DashboardData, ReportData, Session, Transaction, TransactionForm } from './types'

let csrfToken: string | null = null
export function setCsrfToken(token: string | null) { csrfToken = token }

export class ApiError extends Error {
  constructor(message: string, public status: number) { super(message) }
}

async function fetchApi(path: string, init: RequestInit = {}): Promise<Response> {
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
    if (response.status === 401 && path !== '/auth/login') {
      setCsrfToken(null)
      window.dispatchEvent(new Event('gharkhata:session-expired'))
    }
    throw new ApiError(message, response.status)
  }
  return response
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetchApi(path, init)
  if (response.status === 204) return undefined as T
  return response.json() as Promise<T>
}

type ReportFormat = 'csv' | 'xlsx' | 'docx' | 'pdf'
type ReportType = 'monthly' | 'yearly' | 'custom' | 'transactions'
type ExportFilters = { start: string; end: string; format: ReportFormat; reportType: ReportType; month?: string; year?: number }
function reportQuery(start: string, end: string) {
  return new URLSearchParams({ start_date: start, end_date: end }).toString()
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
  add: (transaction: TransactionForm, idempotencyKey?: string) => request<Transaction>('/transactions', {
    method: 'POST', body: JSON.stringify(transaction),
    ...(idempotencyKey ? { headers: { 'Idempotency-Key': idempotencyKey } } : {}),
  }),
  edit: (id: string, transaction: TransactionForm) => request<Transaction>(`/transactions/${id}`, { method: 'PUT', body: JSON.stringify(transaction) }),
  delete: (id: string) => request<void>(`/transactions/${id}`, { method: 'DELETE' }),
  report: (start: string, end: string) => request<ReportData>(`/reports?${reportQuery(start, end)}`),
  async downloadReport(filters: ExportFilters): Promise<{ blob: Blob; filename: string }> {
    const query = new URLSearchParams({
      start_date: filters.start, end_date: filters.end, format: filters.format,
      report_type: filters.reportType,
    })
    if (filters.reportType === 'monthly' && filters.month) query.set('month', filters.month)
    if (filters.reportType === 'yearly' && filters.year) query.set('year', String(filters.year))
    const response = await fetchApi(`/reports/export?${query}`)
    const header = response.headers.get('Content-Disposition') || ''
    const filename = /filename="([A-Za-z0-9_.-]+)"/.exec(header)?.[1] ||
      `GharKhata_${filters.reportType}_${filters.start}_to_${filters.end}.${filters.format}`
    return { blob: await response.blob(), filename }
  },
}
