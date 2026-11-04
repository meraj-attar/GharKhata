import { useEffect, useId, useState, type FormEvent } from 'react'
import { ArrowDownLeft, ArrowUpRight, X } from 'lucide-react'
import { api } from '../lib/api'
import { localDateISO } from '../lib/format'
import type { Category, Transaction, TransactionForm, TransactionType } from '../lib/types'
import { expenseCategories } from '../lib/types'
import { ErrorMessage } from './Shared'

export default function TransactionModal({ edit, onClose, onSaved }: {
  edit: Transaction | null; onClose: () => void; onSaved: () => void
}) {
  const titleId = useId()
  const [form, setForm] = useState<TransactionForm>(() => edit ? {
    type: edit.type, amount: edit.amount, category: edit.category,
    date: edit.date, description: edit.description,
  } : { type: 'expense', amount: '', category: 'Grocery', date: localDateISO(), description: '' })
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    function onKey(e: KeyboardEvent) { if (e.key === 'Escape' && !busy) onClose() }
    document.addEventListener('keydown', onKey)
    const previous = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => { document.removeEventListener('keydown', onKey); document.body.style.overflow = previous }
  }, [onClose, busy])

  function selectType(type: TransactionType) {
    setForm(current => ({ ...current, type, category: type === 'income' ? 'Income' : 'Grocery' }))
  }
  async function submit(e: FormEvent) {
    e.preventDefault()
    setError('')
    const number = Number(form.amount)
    if (!Number.isFinite(number) || number <= 0 || number > 999999999.99 || !/^\d+(?:\.\d{1,2})?$/.test(form.amount)) {
      setError('Enter a positive amount with at most 2 decimal places.'); return
    }
    setBusy(true)
    try {
      const normalized: TransactionForm = { ...form, description: form.description?.trim() || null }
      if (edit) await api.edit(edit.id, normalized)
      else await api.add(normalized)
      onSaved()
    } catch (err) { setError(err instanceof Error ? err.message : 'Could not save the transaction.') }
    finally { setBusy(false) }
  }
  return <div className="fixed inset-0 z-50 flex items-end justify-center bg-navy/45 p-0 backdrop-blur-[2px] sm:items-center sm:p-4" onMouseDown={e => { if (e.target === e.currentTarget && !busy) onClose() }}>
    <section role="dialog" aria-modal="true" aria-labelledby={titleId} className="max-h-[95dvh] w-full overflow-y-auto rounded-t-3xl bg-white p-6 shadow-float sm:max-w-[480px] sm:rounded-3xl sm:p-8">
      <div className="flex items-start justify-between gap-3"><div><p className="eyebrow">HOUSEHOLD FINANCES</p><h2 id={titleId} className="mt-1 text-xl font-extrabold tracking-tight">{edit ? 'Edit transaction' : 'Add transaction'}</h2>
        <p className="mt-1 text-xs text-muted">Keep your records accurate and up to date.</p></div><button className="icon-btn" aria-label="Close" onClick={onClose} disabled={busy}><X size={21}/></button></div>
      <form onSubmit={submit} className="mt-7 space-y-4">
        <div><label className="field-label">Transaction type</label><div className="grid grid-cols-2 gap-2 rounded-2xl bg-canvas p-1.5">
          <button type="button" onClick={() => selectType('income')} className={`flex items-center justify-center gap-2 rounded-xl px-3 py-3 text-sm font-bold transition ${form.type === 'income' ? 'bg-white text-income shadow-sm' : 'text-muted hover:text-navy'}`} aria-pressed={form.type === 'income'}><ArrowDownLeft size={17}/> Income</button>
          <button type="button" onClick={() => selectType('expense')} className={`flex items-center justify-center gap-2 rounded-xl px-3 py-3 text-sm font-bold transition ${form.type === 'expense' ? 'bg-white text-expense shadow-sm' : 'text-muted hover:text-navy'}`} aria-pressed={form.type === 'expense'}><ArrowUpRight size={17}/> Expense</button>
        </div></div>
        <div><label className="field-label" htmlFor="amount">Amount (₹) *</label>
          <div className="relative"><span className="absolute left-4 top-1/2 -translate-y-1/2 font-semibold text-muted">₹</span>
            <input id="amount" className="field pl-9 text-lg font-bold" autoFocus type="number" inputMode="decimal" step="0.01" min="0.01" max="999999999.99" required placeholder="0.00" value={form.amount} onChange={e => setForm({ ...form, amount: e.target.value })}/></div></div>
        <div><label className="field-label" htmlFor="category">Category *</label>
          <select id="category" className="field" value={form.category} disabled={form.type === 'income'} onChange={e => setForm({ ...form, category: e.target.value as Category })}>
            {form.type === 'income' ? <option value="Income">Income</option> : expenseCategories.map(c => <option key={c} value={c}>{c}</option>)}
          </select></div>
        <div><label className="field-label" htmlFor="date">Date *</label><input id="date" type="date" required className="field" value={form.date} onChange={e => setForm({ ...form, date: e.target.value })}/></div>
        <div><label className="field-label" htmlFor="description">Description <span className="font-normal text-muted">(optional)</span></label>
          <textarea id="description" rows={3} maxLength={240} className="field resize-none" placeholder="What was this transaction for?" value={form.description ?? ''} onChange={e => setForm({ ...form, description: e.target.value })}/>
          <p className="mt-1 text-right text-[11px] text-muted">{form.description?.length ?? 0}/240</p></div>
        {error && <ErrorMessage message={error}/>}
        <div className="flex gap-3 pt-1"><button type="button" className="secondary-btn flex-1" onClick={onClose} disabled={busy}>Cancel</button>
          <button type="submit" className="primary-btn flex-1" disabled={busy}>{busy ? 'Saving…' : edit ? 'Save changes' : 'Save transaction'}</button></div>
      </form>
    </section>
  </div>
}
