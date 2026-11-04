export function formatINR(value: string | number): string {
  return new Intl.NumberFormat('en-IN', {
    style: 'currency', currency: 'INR', minimumFractionDigits: 2, maximumFractionDigits: 2,
  }).format(Number(value))
}
export function localDateISO(date = new Date()): string {
  const yyyy = date.getFullYear()
  const mm = String(date.getMonth() + 1).padStart(2, '0')
  const dd = String(date.getDate()).padStart(2, '0')
  return `${yyyy}-${mm}-${dd}`
}
export function monthISO(date = new Date()): string { return localDateISO(date).slice(0, 7) }
export function startOfMonth(month: string): string { return `${month}-01` }
export function endOfMonth(month: string): string {
  const [y, m] = month.split('-').map(Number)
  return localDateISO(new Date(y, m, 0))
}
export function daysBefore(iso: string, days: number): string {
  const [y, m, d] = iso.split('-').map(Number)
  return localDateISO(new Date(y, m - 1, d - days))
}
export function formatDate(iso: string): string {
  const [y, m, d] = iso.split('-').map(Number)
  return new Intl.DateTimeFormat('en-IN', { day: '2-digit', month: 'short', year: 'numeric' }).format(new Date(y, m - 1, d))
}
export function formatMonth(month: string): string {
  const [y, m] = month.split('-').map(Number)
  return new Intl.DateTimeFormat('en-IN', { month: 'long', year: 'numeric' }).format(new Date(y, m - 1, 1))
}
