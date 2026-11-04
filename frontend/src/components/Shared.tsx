import type { ReactNode } from 'react'
import { ArrowDownLeft, ArrowUpRight, ClipboardList, House } from 'lucide-react'
import type { Transaction } from '../lib/types'
import { formatDate, formatINR } from '../lib/format'

export function Brand({ light = false }: { light?: boolean }) {
  return <div className="flex items-center gap-3">
    <div className={`flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl ${light ? 'bg-white/15 text-white' : 'bg-indigo text-white'}`}>
      <House size={22} strokeWidth={2.2} />
    </div>
    <div><div className={`text-[21px] font-extrabold tracking-tight ${light ? 'text-white' : 'text-navy'}`}>Ghar<span className={light ? 'text-lavender' : 'text-indigo'}>Khata</span></div>
      <div className={`-mt-0.5 text-[10px] font-medium tracking-wide ${light ? 'text-white/55' : 'text-muted'}`}>HOUSEHOLD FINANCE MANAGER</div>
    </div>
  </div>
}

export function CategoryIcon({ type, size = 18 }: { type: 'income' | 'expense'; size?: number }) {
  return type === 'income' ? <ArrowDownLeft size={size} /> : <ArrowUpRight size={size} />
}

export function TransactionList({ rows, onEdit, onDelete, compact = false }: {
  rows: Transaction[]; onEdit?: (row: Transaction) => void; onDelete?: (row: Transaction) => void; compact?: boolean
}) {
  if (rows.length === 0) return <EmptyState title="No transactions yet" description="Your saved income and expenses will appear here." />
  return <div className="divide-y divide-line/80">
    {rows.map(row => <div key={row.id} className="flex items-center gap-3 py-3.5 first:pt-0 last:pb-0">
      <div className={`flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl ${row.type === 'income' ? 'bg-green-50 text-income' : 'bg-[#FFF2F2] text-expense'}`}>
        <CategoryIcon type={row.type} />
      </div>
      <div className="min-w-0 flex-1">
        <div className="truncate text-sm font-semibold text-navy">{row.description || row.category}</div>
        <div className="mt-0.5 flex flex-wrap gap-x-2 text-xs text-muted"><span>{row.category}</span><span>·</span><span>{formatDate(row.date)}</span></div>
      </div>
      <div className="shrink-0 text-right">
        <div className={`text-sm font-bold tabular-nums ${row.type === 'income' ? 'text-income' : 'text-navy'}`}>
          {row.type === 'income' ? '+' : '−'}{formatINR(row.amount)}
        </div>
        {!compact && (onEdit || onDelete) && <div className="mt-1 flex justify-end gap-3 text-xs">
          {onEdit && <button className="font-semibold text-indigo hover:underline" onClick={() => onEdit(row)}>Edit</button>}
          {onDelete && <button className="font-semibold text-expense hover:underline" onClick={() => onDelete(row)}>Delete</button>}
        </div>}
      </div>
    </div>)}
  </div>
}

export function EmptyState({ title, description, action }: { title: string; description: string; action?: ReactNode }) {
  return <div className="flex min-h-[190px] flex-col items-center justify-center px-5 py-9 text-center">
    <div className="mb-4 flex h-14 w-14 items-center justify-center rounded-2xl bg-canvas text-indigo"><ClipboardList size={24} strokeWidth={1.7} /></div>
    <div className="text-sm font-bold text-navy">{title}</div>
    <p className="mt-1.5 max-w-[280px] text-xs leading-relaxed text-muted">{description}</p>
    {action && <div className="mt-4">{action}</div>}
  </div>
}

export function ErrorMessage({ message, retry }: { message: string; retry?: () => void }) {
  return <div role="alert" className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-red-100 bg-red-50 px-4 py-3 text-sm text-red-700">
    <span>{message}</span>{retry && <button onClick={retry} className="font-semibold underline">Try again</button>}
  </div>
}

export function Loading() {
  return <div className="flex min-h-48 items-center justify-center" role="status" aria-label="Loading">
    <div className="h-8 w-8 animate-spin rounded-full border-[3px] border-lavender/40 border-t-indigo" />
  </div>
}

export function MoneyCard({ label, value, icon, tone, subtitle }: {
  label: string; value: string; icon: ReactNode; tone: 'income' | 'expense' | 'balance'; subtitle: string
}) {
  const styles = {
    income: 'bg-green-50 text-income', expense: 'bg-[#FFF2F2] text-expense', balance: 'bg-indigo/10 text-indigo',
  }
  return <section className="surface flex min-w-0 flex-col justify-between p-5 sm:p-6">
    <div className="flex items-start justify-between gap-3"><span className="text-sm font-medium text-muted">{label}</span>
      <span className={`flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl ${styles[tone]}`}>{icon}</span>
    </div>
    <div className="mt-6 break-words text-[clamp(1.4rem,2.5vw,1.9rem)] font-extrabold tracking-tight tabular-nums text-navy">{formatINR(value)}</div>
    <div className="mt-2 text-xs text-muted">{subtitle}</div>
  </section>
}
