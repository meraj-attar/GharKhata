import { useEffect, useState } from 'react'
import { ArrowDownLeft, ArrowUpRight, CalendarRange, Download, Wallet, FileSpreadsheet, FileText, FileDown, CheckCircle2 } from 'lucide-react'
import { api } from '../lib/api'
import { daysBefore, endOfMonth, formatDate, formatINR, localDateISO, monthISO, startOfMonth } from '../lib/format'
import type { ReportData } from '../lib/types'
import { EmptyState, ErrorMessage, Loading, MoneyCard, TransactionList } from './Shared'

type Period = 1 | 5 | 10 | 20 | 'monthly' | 'yearly' | 'custom'
type ExportType = 'monthly' | 'yearly' | 'custom' | 'transactions'
type ExportFormat = 'xlsx' | 'docx' | 'pdf'
const periods: { id: Period; label: string }[] = [
  { id: 1, label: '1 Day' }, { id: 5, label: '5 Days' }, { id: 10, label: '10 Days' },
  { id: 20, label: '20 Days' }, { id: 'monthly', label: 'Monthly' },
  { id: 'yearly', label: 'Yearly' }, { id: 'custom', label: 'Custom' },
]
export default function Reports({ refreshVersion }: { refreshVersion: number }) {
  const [period, setPeriod] = useState<Period>('monthly')
  const [endDate, setEndDate] = useState(localDateISO())
  const [month, setMonth] = useState(monthISO())
  const [year, setYear] = useState(new Date().getFullYear())
  const [exportType, setExportType] = useState<ExportType>('monthly')
  const [exportFormat, setExportFormat] = useState<ExportFormat>('xlsx')
  const [downloadSuccess, setDownloadSuccess] = useState('')
  const [customStart, setCustomStart] = useState(daysBefore(localDateISO(), 29))
  const [customEnd, setCustomEnd] = useState(localDateISO())
  const [data, setData] = useState<ReportData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [downloading, setDownloading] = useState(false)
  const [downloadError, setDownloadError] = useState('')
  const start = period === 'monthly' ? startOfMonth(month)
    : period === 'yearly' ? `${year}-01-01`
    : period === 'custom' ? customStart : daysBefore(endDate, period - 1)
  const end = period === 'monthly' ? endOfMonth(month)
    : period === 'yearly' ? `${year}-12-31` : period === 'custom' ? customEnd : endDate
  const datesValid = Boolean(start && end && start <= end && year >= 1 && year <= 9999)

  useEffect(() => {
    let active = true
    setError(''); setDownloadError(''); setDownloadSuccess('')
    if (!datesValid) { setData(null); setLoading(false); return () => { active = false } }
    setLoading(true)
    api.report(start, end).then(result => { if (active) setData(result) })
      .catch(err => { if (active) setError(err.message) })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [start, end, datesValid, refreshVersion])

  function choosePeriod(next: Period) {
    setPeriod(next)
    setExportType(next === 'monthly' || next === 'yearly' || next === 'custom' ? next : 'transactions')
  }
  function chooseExportType(next: ExportType) {
    setExportType(next)
    if (next !== 'transactions') setPeriod(next)
  }
  async function download(format: ExportFormat | 'csv') {
    if (!datesValid || loading || error || downloading) return
    setDownloading(true); setDownloadError(''); setDownloadSuccess('')
    try {
      const result = await api.downloadReport({
        start, end, format, reportType: format === 'csv' ? 'custom' : exportType,
        month, year,
      })
      const url = URL.createObjectURL(result.blob)
      const link = document.createElement('a')
      link.href = url
      link.download = result.filename
      document.body.appendChild(link)
      link.click()
      link.remove()
      window.setTimeout(() => URL.revokeObjectURL(url), 1000)
      setDownloadSuccess(`Your ${format.toUpperCase()} report has been downloaded.`)
    } catch (err) {
      setDownloadError(err instanceof Error ? err.message : 'Unable to download report.')
    } finally { setDownloading(false) }
  }
  return <div className="space-y-6">
    <div><p className="eyebrow">YOUR MONEY, IN DETAIL</p><h2 className="mt-1.5 text-[23px] font-bold tracking-tight">Reports & downloads</h2>
      <p className="mt-1 text-sm text-muted">Review your finances and download Excel, Word, PDF or CSV reports.</p></div>
    <section className="surface p-5 sm:p-6">
      <div className="mb-4 flex items-center gap-2"><CalendarRange size={18} className="text-indigo"/><h3 className="section-title">Select report period</h3></div>
      <div className="flex flex-wrap gap-2" aria-label="Report period">{periods.map(option => <button key={option.id} type="button" aria-pressed={period === option.id} onClick={() => choosePeriod(option.id)} className={`rounded-xl border px-4 py-2.5 text-xs font-bold transition ${period === option.id ? 'border-indigo bg-indigo text-white shadow-sm' : 'border-line bg-white text-muted hover:border-lavender hover:text-indigo'}`}>{option.label}</button>)}</div>
      <div className="mt-5 flex flex-wrap gap-4 border-t border-line pt-5">
        {typeof period === 'number' ? <div className="min-w-[210px]"><label className="field-label" htmlFor="report-end">End date</label><input id="report-end" type="date" className="field" value={endDate} onChange={e => setEndDate(e.target.value)}/></div> : period === 'yearly' ?
          <div className="min-w-[210px]"><label className="field-label" htmlFor="report-year">Report year</label><input id="report-year" type="number" min="1" max="9999" className="field" value={year} onChange={e => setYear(Number(e.target.value))}/></div> : period === 'monthly' ?
          <div className="min-w-[210px]"><label className="field-label" htmlFor="report-month">Report month</label><input id="report-month" type="month" className="field" value={month} onChange={e => setMonth(e.target.value)}/></div> : <>
            <div className="min-w-[190px]"><label className="field-label" htmlFor="report-start">Start date</label><input id="report-start" type="date" className="field" value={customStart} onChange={e => setCustomStart(e.target.value)}/></div>
            <div className="min-w-[190px]"><label className="field-label" htmlFor="report-custom-end">End date</label><input id="report-custom-end" type="date" className="field" value={customEnd} onChange={e => setCustomEnd(e.target.value)}/></div>
          </>}
        {datesValid && <div className="flex flex-col justify-end pb-1"><span className="text-[11px] font-medium text-muted">Showing transactions from</span><span className="mt-1 text-xs font-bold text-navy">{formatDate(start)} – {formatDate(end)}</span></div>}
      </div>
      {!datesValid && <p role="alert" className="mt-3 text-sm font-semibold text-expense">Select valid dates. The start date must not be after the end date.</p>}
    </section>

    <section className="surface p-5 sm:p-6" aria-labelledby="export-title">
      <div className="flex items-center gap-2"><FileDown size={19} className="text-indigo"/><h3 className="section-title" id="export-title">Export Financial Report</h3></div>
      <p className="mt-1 text-xs text-muted">Choose the report and file format. Downloads include only your financial records.</p>
      <div className="mt-5">
        <label className="field-label" htmlFor="export-type">Report type</label>
        <select id="export-type" className="field max-w-sm" value={exportType} onChange={e => chooseExportType(e.target.value as ExportType)}>
          <option value="monthly">Monthly financial report</option>
          <option value="yearly">Yearly financial report</option>
          <option value="custom">Custom date range report</option>
          <option value="transactions">Transaction report (selected period)</option>
        </select>
        <p className="mt-2 text-xs text-muted">{exportType === 'transactions' ? 'Uses the dates selected above.' : 'Use the report period controls above to choose the month, year or custom dates.'}</p>
      </div>
      <div className="mt-5"><p className="field-label">File format</p>
        <div className="grid gap-2 sm:grid-cols-3" role="group" aria-label="Export file format">
          {([
            { key: 'xlsx' as const, label: 'Excel (.xlsx)', Icon: FileSpreadsheet },
            { key: 'docx' as const, label: 'Word (.docx)', Icon: FileText },
            { key: 'pdf' as const, label: 'PDF (.pdf)', Icon: FileDown },
          ]).map(({ key, label, Icon }) => <button key={key} type="button" aria-pressed={exportFormat === key}
            onClick={() => setExportFormat(key)} className={`flex items-center gap-2 rounded-xl border px-4 py-3 text-sm font-semibold transition ${exportFormat === key ? 'border-indigo bg-indigo/10 text-indigo' : 'border-line bg-white text-muted hover:border-lavender'}`}>
              <Icon size={18}/>{label}
          </button>)}
        </div>
      </div>
      <div className="mt-5 flex flex-wrap items-center gap-3">
        <button className="primary-btn" type="button" onClick={() => void download(exportFormat)} disabled={!datesValid || loading || downloading}>
          <Download size={17}/>{downloading ? 'Generating your report…' : 'Download Report'}
        </button>
        {data?.transactions.length === 0 && <span className="text-xs text-muted">No transactions in this period; your report will show zero totals.</span>}
      </div>
      {downloadError && <div className="mt-4"><ErrorMessage message={downloadError}/></div>}
      {downloadSuccess && <p role="status" className="mt-4 flex items-center gap-2 text-sm font-semibold text-income"><CheckCircle2 size={17}/>{downloadSuccess}</p>}
    </section>
    {error && <ErrorMessage message={error}/>}
    {datesValid && !error && (loading || !data ? <Loading/> : <>
      <div className="flex flex-wrap items-center justify-between gap-3"><div><p className="eyebrow">PERIOD SUMMARY</p><h3 className="mt-1 text-base font-bold">{formatDate(start)} – {formatDate(end)}</h3></div>
        <button className="secondary-btn" onClick={() => void download('csv')} disabled={downloading}><Download size={17}/>{downloading ? 'Preparing…' : 'Download CSV'}</button></div>
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
