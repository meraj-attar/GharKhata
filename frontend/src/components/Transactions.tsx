import { useEffect, useState } from 'react'
import { ChevronLeft, ChevronRight, FilterX, Pencil, Plus, Search, Trash2 } from 'lucide-react'
import { api } from '../lib/api'
import { formatDate, formatINR } from '../lib/format'
import { expenseCategories, type Transaction } from '../lib/types'
import { CategoryIcon, EmptyState, ErrorMessage, Loading, TransactionList } from './Shared'

const PAGE_SIZE = 15
export default function Transactions({ refreshVersion, onAdd, onEdit }: {
  refreshVersion: number; onAdd: () => void; onEdit: (row: Transaction) => void
}) {
  const [rows, setRows] = useState<Transaction[]>([])
  const [month, setMonth] = useState('')
  const [type, setType] = useState('')
  const [category, setCategory] = useState('')
  const [search, setSearch] = useState('')
  const [debouncedSearch, setDebouncedSearch] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [deleteTarget, setDeleteTarget] = useState<Transaction | null>(null)
  const [deleting, setDeleting] = useState(false)
  const [deleteError, setDeleteError] = useState('')
  const [page, setPage] = useState(1)
  const [listVersion, setListVersion] = useState(0)
  useEffect(() => { const timer = window.setTimeout(() => setDebouncedSearch(search.trim()), 300); return () => clearTimeout(timer) }, [search])
  useEffect(() => { setPage(1) }, [month, type, category, debouncedSearch])
  useEffect(() => {
    let active = true; setLoading(true); setError('')
    api.transactions({ month, type, category, search: debouncedSearch })
      .then(result => { if (active) setRows(result) })
      .catch(err => { if (active) setError(err.message) })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [month, type, category, debouncedSearch, refreshVersion, listVersion])
  async function confirmDelete() {
    if (!deleteTarget) return
    setDeleting(true); setDeleteError('')
    try { await api.delete(deleteTarget.id); setDeleteTarget(null); setListVersion(n => n + 1) }
    catch (err) { setDeleteError(err instanceof Error ? err.message : 'Unable to delete transaction.') }
    finally { setDeleting(false) }
  }
  const count = rows.length
  const pages = Math.max(1, Math.ceil(count / PAGE_SIZE))
  const currentPage = Math.min(page, pages)
  const visible = rows.slice((currentPage - 1) * PAGE_SIZE, currentPage * PAGE_SIZE)
  return <div className="space-y-6">
    <div className="flex flex-wrap items-center justify-between gap-4"><div><p className="eyebrow">YOUR FINANCIAL RECORDS</p><h2 className="mt-1.5 text-[23px] font-bold tracking-tight">All transactions</h2>
      <p className="mt-1 text-sm text-muted">Find, review, and manage your entries.</p></div>
      <button className="primary-btn" onClick={onAdd}><Plus size={18}/> Add transaction</button></div>
    <section className="surface p-4 sm:p-6">
      <div className="grid gap-3 md:grid-cols-[1.5fr_1fr_1fr_1fr]">
        <div className="relative"><Search size={17} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-muted"/>
          <input aria-label="Search transactions" className="field pl-10" placeholder="Search description or category" value={search} onChange={e => setSearch(e.target.value)} maxLength={100}/></div>
        <input aria-label="Filter by month" type="month" className="field" value={month} onChange={e => setMonth(e.target.value)}/>
        <select aria-label="Filter by type" className="field" value={type} onChange={e => setType(e.target.value)}><option value="">All types</option><option value="income">Income</option><option value="expense">Expense</option></select>
        <select aria-label="Filter by category" className="field" value={category} onChange={e => setCategory(e.target.value)}><option value="">All categories</option><option value="Income">Income</option>{expenseCategories.map(c => <option key={c}>{c}</option>)}</select>
      </div>
      {(month || type || category || search) && <button className="mt-3 inline-flex items-center gap-1.5 text-xs font-semibold text-indigo hover:underline" onClick={() => { setMonth(''); setType(''); setCategory(''); setSearch('') }}><FilterX size={14}/> Clear filters</button>}
      <div className="mt-6 flex items-center justify-between border-b border-line pb-4"><div className="text-sm font-bold">Transaction history</div><span className="text-xs text-muted">{count} {count === 1 ? 'transaction' : 'transactions'}</span></div>
      {error ? <div className="py-5"><ErrorMessage message={error} retry={() => setListVersion(n => n + 1)} /></div> : loading ? <Loading/> : count === 0 ?
        <EmptyState title="No matching transactions" description={month || type || category || search ? 'Try changing your search or filters.' : 'Add your first income or expense to get started.'} action={<button className="text-xs font-bold text-indigo hover:underline" onClick={onAdd}>Add transaction</button>}/> : <>
          <div className="hidden overflow-x-auto md:block"><table className="w-full min-w-[680px] border-collapse text-left">
            <thead><tr className="text-[11px] font-semibold uppercase tracking-wider text-muted"><th className="py-4 font-semibold">Transaction</th><th className="py-4 font-semibold">Date</th><th className="py-4 font-semibold">Category</th><th className="py-4 text-right font-semibold">Amount</th><th className="py-4 text-right font-semibold">Actions</th></tr></thead>
            <tbody className="divide-y divide-line/80">{visible.map(row => <tr key={row.id} className="group hover:bg-canvas/40">
              <td className="py-3.5"><div className="flex items-center gap-3"><div className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-xl ${row.type === 'income' ? 'bg-green-50 text-income' : 'bg-[#FFF2F2] text-expense'}`}><CategoryIcon type={row.type} size={16}/></div>
                <div><div className="max-w-[250px] truncate text-sm font-semibold">{row.description || row.category}</div><span className="text-[11px] capitalize text-muted">{row.type}</span></div></div></td>
              <td className="py-3.5 text-xs text-muted">{formatDate(row.date)}</td>
              <td className="py-3.5"><span className="rounded-lg bg-canvas px-2.5 py-1.5 text-xs font-medium text-navy">{row.category}</span></td>
              <td className={`py-3.5 text-right text-sm font-bold tabular-nums ${row.type === 'income' ? 'text-income' : 'text-navy'}`}>{row.type === 'income' ? '+' : '−'}{formatINR(row.amount)}</td>
              <td className="py-3.5 text-right"><button className="icon-btn" aria-label={`Edit ${row.description || row.category}`} title="Edit" onClick={() => onEdit(row)}><Pencil size={16}/></button><button className="icon-btn hover:text-expense" aria-label={`Delete ${row.description || row.category}`} title="Delete" onClick={() => setDeleteTarget(row)}><Trash2 size={16}/></button></td>
            </tr>)}</tbody>
          </table></div>
          <div className="pt-4 md:hidden"><TransactionList rows={visible} onEdit={onEdit} onDelete={setDeleteTarget}/></div>
          {pages > 1 && <div className="mt-4 flex items-center justify-between border-t border-line pt-4"><span className="text-xs text-muted">Page {currentPage} of {pages}</span><div className="flex gap-2"><button className="secondary-btn !p-2" aria-label="Previous page" disabled={currentPage <= 1} onClick={() => setPage(n => n - 1)}><ChevronLeft size={17}/></button><button className="secondary-btn !p-2" aria-label="Next page" disabled={currentPage >= pages} onClick={() => setPage(n => n + 1)}><ChevronRight size={17}/></button></div></div>}
        </>}
    </section>
    {deleteTarget && <div className="fixed inset-0 z-50 flex items-center justify-center bg-navy/45 px-4" onMouseDown={e => { if (e.target === e.currentTarget && !deleting) setDeleteTarget(null) }}>
      <div role="alertdialog" aria-modal="true" aria-labelledby="delete-title" aria-describedby="delete-desc" className="w-full max-w-[410px] rounded-3xl bg-white p-7 shadow-float">
        <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-2xl bg-[#FFF2F2] text-expense"><Trash2 size={22}/></div>
        <h3 id="delete-title" className="text-lg font-bold">Delete transaction?</h3><p id="delete-desc" className="mt-2 text-sm leading-relaxed text-muted">This will permanently remove {deleteTarget.description ? `“${deleteTarget.description}”` : `this ${deleteTarget.category} transaction`} for {formatINR(deleteTarget.amount)}. Your totals will be updated.</p>
        {deleteError && <div className="mt-4"><ErrorMessage message={deleteError}/></div>}
        <div className="mt-6 flex gap-3"><button className="secondary-btn flex-1" disabled={deleting} onClick={() => setDeleteTarget(null)}>Cancel</button><button className="inline-flex flex-1 items-center justify-center rounded-xl bg-expense px-4 py-2.5 text-sm font-bold text-white transition hover:bg-red-500" disabled={deleting} onClick={confirmDelete}>{deleting ? 'Deleting…' : 'Delete'}</button></div>
      </div></div>}
  </div>
}
