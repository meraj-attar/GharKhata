import { useEffect, useState } from 'react'
import { ArrowDownLeft, ArrowUpRight, CalendarRange, Download, Wallet } from 'lucide-react'
import { api } from '../lib/api'
import { daysBefore, endOfMonth, formatDate, formatINR, localDateISO, monthISO, startOfMonth } from '../lib/format'
import type { ReportData } from '../lib/types'
import { EmptyState, ErrorMessage, Loading, MoneyCard, TransactionList } from './Shared'

type Period = 1 | 5 | 10 | 20 | 'monthly' | 'custom'
const periods: { id: Period; label: string }[] = [
  { id: 1, label: '1 Day' }, { id: 5, label: '5 Days' }, { id: 10, label: '10 Days' },
  { id: 20, label: '20 Days' }, { id: 'monthly', label: 'Monthly' }, { id: 'custom', label: 'Custom' },
]
export default function Reports({ refreshVersion }: { refreshVersion: number }) {
  const [period, setPeriod] = useState<Period>('monthly')
  const [endDate, setEndDate] = useState(localDateISO())
  const [month, setMonth] = useState(monthISO())
  const [customStart, setCustomStart] = useState(daysBefore(localDateISO(), 29))
  const [customEnd, setCustomEnd] = useState(localDateISO())
  const [data, setData] = useState<ReportData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [downloading, setDownloading] = useState(false)
  const [downloadError, setDownloadError] = useState('')
  const start = period === 'monthly' ? startOfMonth(month)
    : period === 'custom' ? customStart : daysBefore(endDate, period - 1)
  const end = period === 'monthly' ? endOfMonth(month) : period === 'custom' ? customEnd : endDate
  const datesValid = Boolean(start && end && start <= end)

  useEffect(() => {
    let active = true
    setError(''); setDownloadError('')
    if (!datesValid) { setData(null); setLoading(false); return () => { active = false } }
    setLoading(true)
    api.report(start, end).then(result => { if (active) setData(result) })
      .catch(err => { if (active) setError(err.message) })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [start, end, datesValid, refreshVersion])

  async function download() {
    if (!datesValid || loading || error) return
    setDownloading(true); setDownloadError('')
    try {
      const response = await fetch(api.reportDownloadUrl(start, end), { credentials: 'same-origin' })
      if (!response.ok) throw new Error(response.status === 401 ? 'Session expired. Please sign in again.' : 'Unable to download report.')
      const blob = await response.blob()
      const url = URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.download = `GharKhata_${start}_to_${end}.csv`
      document.body.appendChild(link)
      link.click()
      link.remove()
      URL.revokeObjectURL(url)
    } catch (err) { setDownloadError(err instanceof Error ? err.message : 'Unable to download report.') }
    finally { setDownloading(false) }
  }
  return <div className="space-y-6">
    <div><p className="eyebrow">YOUR MONEY, IN DETAIL</p><h2 className="mt-1.5 text-[23px] font-bold tracking-tight">Reports & downloads</h2>
      <p className="mt-1 text-sm text-muted">Review any period and export your records as CSV.</p></div>
    <section className="surface p-5 sm:p-6">
      <div className="mb-4 flex items-center gap-2"><CalendarRange size={18} className="text-indigo"/><h3 className="section-title">Select report period</h3></div>
      <div className="flex flex-wrap gap-2" aria-label="Report period">{periods.map(option => <button key={option.id} type="button" aria-pressed={period === option.id} onClick={() => setPeriod(option.id)} className={`rounded-xl border px-4 py-2.5 text-xs font-bold transition ${period === option.id ? 'border-indigo bg-indigo text-white shadow-sm' : 'border-line bg-white text-muted hover:border-lavender hover:text-indigo'}`}>{option.label}</button>)}</div>
      <div className="mt-5 flex flex-wrap gap-4 border-t border-line pt-5">
        {typeof period === 'number' ? <div className="min-w-[210px]"><label className="field-label" htmlFor="report-end">End date</label><input id="report-end" type="date" className="field" value={endDate} onChange={e => setEndDate(e.target.value)}/></div> : period === 'monthly' ?
          <div className="min-w-[210px]"><label className="field-label" htmlFor="report-month">Report month</label><input id="report-month" type="month" className="field" value={month} onChange={e => setMonth(e.target.value)}/></div> : <>
            <div className="min-w-[190px]"><label className="field-label" htmlFor="report-start">Start date</label><input id="report-start" type="date" className="field" value={customStart} onChange={e => setCustomStart(e.target.value)}/></div>
            <div className="min-w-[190px]"><label className="field-label" htmlFor="report-custom-end">End date</label><input id="report-custom-end" type="date" className="field" value={customEnd} onChange={e => setCustomEnd(e.target.value)}/></div>
          </>}
        {datesValid && <div className="flex flex-col justify-end pb-1"><span className="text-[11px] font-medium text-muted">Showing transactions from</span><span className="mt-1 text-xs font-bold text-navy">{formatDate(start)} – {formatDate(end)}</span></div>}
      </div>
      {!datesValid && <p role="alert" className="mt-3 text-sm font-semibold text-expense">Select valid dates. The start date must not be after the end date.</p>}
    </section>
    {downloadError && <ErrorMessage message={downloadError}/>}
    {error && <ErrorMessage message={error}/>}
    {datesValid && !error && (loading || !data ? <Loading/> : <>
      <div className="flex flex-wrap items-center justify-between gap-3"><div><p className="eyebrow">PERIOD SUMMARY</p><h3 className="mt-1 text-base font-bold">{formatDate(start)} – {formatDate(end)}</h3></div>
        <button className="primary-btn" onClick={download} disabled={downloading}><Download size={17}/>{downloading ? 'Preparing…' : 'Download CSV'}</button></div>
      <div className="grid gap-4 sm:grid-cols-3">
        <MoneyCard label="Total Income" value={data.total_income} tone="income" icon={<ArrowDownLeft size={21}/>} subtitle="Income in this period" />
        <MoneyCard label="Total Expenses" value={data.total_expenses} tone="expense" icon={<ArrowUpRight size={21}/>} subtitle="Expenses in this period" />
        <MoneyCard label="Remaining Balance" value={data.remaining_balance} tone="balance" icon={<Wallet size={21}/>} subtitle="Income − expenses in this period" />
      </div>
      <div className="grid gap-5 lg:grid-cols-[.85fr_1.15fr]">
        <section className="surface p-5 sm:p-6"><h3 className="section-title">Category breakdown</h3><p className="mt-1 text-xs text-muted">Expenses during your selected period</p>
          {data.categories.length === 0 ? <EmptyState title="No expenses recorded" description="No expense categories were found for this period."/> :
            <div className="mt-6 space-y-4">{data.categories.map(row => <div key={row.category} className="flex items-center justify-between gap-3 border-b border-line/70 pb-3 last:border-0">
              <span className="text-sm font-semibold">{row.category}</span><div className="text-right"><span className="text-sm font-bold tabular-nums">{formatINR(row.amount)}</span><span className="ml-2 text-xs text-muted">{Math.round(Number(row.amount) / Number(data.total_expenses) * 100)}%</span></div>
            </div>)}</div>}</section>
        <section className="surface p-5 sm:p-6"><div className="flex justify-between gap-3"><div><h3 className="section-title">Transactions in this period</h3><p className="mt-1 text-xs text-muted">Only entries within your chosen dates</p></div><span className="text-xs font-medium text-muted">{data.transactions.length} entries</span></div>
          <div className="mt-5"><TransactionList rows={data.transactions} compact/></div></section>
      </div>
    </>)}
  </div>
}
