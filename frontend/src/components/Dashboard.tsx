import { useEffect, useState } from 'react'
import { ArrowDownLeft, ArrowUpRight, CalendarDays, ChevronRight, Plus, Wallet } from 'lucide-react'
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { api } from '../lib/api'
import { formatINR, formatMonth } from '../lib/format'
import type { DashboardData } from '../lib/types'
import { EmptyState, ErrorMessage, Loading, MoneyCard, TransactionList } from './Shared'

const categoryColors = ['#4F46E5', '#818CF8', '#A5B4FC', '#E57373', '#64748B', '#C4B5FD']
export default function Dashboard({ month, refreshVersion, onAdd, onTransactions }: {
  month: string; refreshVersion: number; onAdd: () => void; onTransactions: () => void
}) {
  const [data, setData] = useState<DashboardData | null>(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)
  useEffect(() => {
    let active = true
    setLoading(true); setError('')
    api.dashboard(month).then(result => { if (active) setData(result) })
      .catch(err => { if (active) setError(err.message) })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [month, refreshVersion])
  if (loading) return <Loading />
  if (error) return <ErrorMessage message={error} retry={() => window.location.reload()} />
  if (!data) return null
  const hasExpenses = Number(data.total_expenses) > 0
  const maxCategory = Math.max(1, ...data.categories.map(item => Number(item.amount)))
  return <div className="space-y-6">
    <div className="flex flex-wrap items-center justify-between gap-4">
      <div><div className="eyebrow flex items-center gap-2"><CalendarDays size={13} /> YOUR MONTH AT A GLANCE</div>
        <h2 className="mt-1.5 text-[22px] font-bold tracking-tight sm:text-2xl">{formatMonth(month)} overview</h2>
        <p className="mt-1 text-sm text-muted">A simple, clear picture of your household finances.</p></div>
      <button className="primary-btn" onClick={onAdd}><Plus size={18} /> Add transaction</button>
    </div>
    <div className="grid gap-4 sm:grid-cols-3">
      <MoneyCard label="Total Income" value={data.total_income} tone="income" icon={<ArrowDownLeft size={22}/>} subtitle="Income this month" />
      <MoneyCard label="Total Expenses" value={data.total_expenses} tone="expense" icon={<ArrowUpRight size={22}/>} subtitle="Expenses this month" />
      <MoneyCard label="Remaining Balance" value={data.remaining_balance} tone="balance" icon={<Wallet size={22}/>} subtitle="Income − expenses this month" />
    </div>
    <div className="grid grid-cols-1 gap-5 xl:grid-cols-[1.45fr_1fr]">
      <section className="surface min-w-0 p-5 sm:p-6">
        <div className="mb-6 flex items-start justify-between gap-2"><div><h3 className="section-title">Monthly expense overview</h3>
          <p className="mt-1 text-xs text-muted">Daily spending through {formatMonth(month)}</p></div>
          <span className="rounded-full bg-canvas px-3 py-1.5 text-[11px] font-semibold text-indigo">Daily</span></div>
        {hasExpenses ? <div className="h-[250px] w-full" aria-label="Bar chart of daily expenses">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={data.daily_expenses.map(d => ({ day: d.day, amount: Number(d.amount) }))} margin={{ top: 8, right: 0, left: -18, bottom: 0 }}>
              <CartesianGrid vertical={false} stroke="#E8EAF2" strokeDasharray="3 4" />
              <XAxis dataKey="day" axisLine={false} tickLine={false} interval="preserveStartEnd" tick={{ fill: '#94A3B8', fontSize: 10 }} minTickGap={18} />
              <YAxis axisLine={false} tickLine={false} width={50} tick={{ fill: '#94A3B8', fontSize: 10 }} tickFormatter={value => `₹${Number(value) >= 1000 ? `${(Number(value) / 1000).toFixed(0)}k` : value}`} />
              <Tooltip cursor={{ fill: '#F5F3FF' }} formatter={value => [formatINR(Number(value)), 'Expenses'] as [string, string]} labelFormatter={value => `Day ${value}`} contentStyle={{ border: '1px solid #E8EAF2', borderRadius: 12, boxShadow: '0 8px 24px #17255412', fontSize: 12 }} />
              <Bar dataKey="amount" fill="#818CF8" radius={[5, 5, 0, 0]} maxBarSize={20} />
            </BarChart>
          </ResponsiveContainer>
        </div> : <EmptyState title="No expenses this month" description="Add an expense to see your spending trend here." action={<button onClick={onAdd} className="text-xs font-bold text-indigo hover:underline">Add an expense</button>} />}
      </section>
      <section className="surface min-w-0 p-5 sm:p-6">
        <div className="mb-6"><h3 className="section-title">Expenses by category</h3>
          <p className="mt-1 text-xs text-muted">Where your money went this month</p></div>
        {hasExpenses ? <div className="space-y-5">
          {data.categories.map((row, index) => {
            const value = Number(row.amount)
            const ratio = Number(data.total_expenses) ? Math.round(value / Number(data.total_expenses) * 100) : 0
            return <div key={row.category}>
              <div className="mb-2 flex items-center justify-between gap-3 text-xs"><div className="flex min-w-0 items-center gap-2 font-semibold text-navy"><span className="h-2.5 w-2.5 rounded-full" style={{ background: categoryColors[index % categoryColors.length] }}/>{row.category}</div>
                <div className="shrink-0 font-medium text-muted">{formatINR(value)} <span className="ml-1 text-[10px]">{ratio}%</span></div></div>
              <div className="h-2 overflow-hidden rounded-full bg-canvas"><div className="h-full rounded-full transition-[width] duration-300" style={{ width: `${value / maxCategory * 100}%`, background: categoryColors[index % categoryColors.length] }} /></div>
            </div>
          })}
        </div> : <EmptyState title="No category data" description="Your spending categories will appear as you record expenses." />}
      </section>
    </div>
    <section className="surface p-5 sm:p-6">
      <div className="mb-5 flex items-center justify-between gap-4"><div><h3 className="section-title">Recent transactions</h3><p className="mt-1 text-xs text-muted">Your latest entries for this month</p></div>
        <button onClick={onTransactions} className="inline-flex items-center gap-1 text-xs font-bold text-indigo hover:underline">View all <ChevronRight size={15}/></button></div>
      <TransactionList compact rows={data.recent_transactions} />
    </section>
  </div>
}
