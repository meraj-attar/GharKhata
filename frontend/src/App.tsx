import { useCallback, useEffect, useState, type FormEvent } from 'react'
import { CalendarDays, ChartNoAxesCombined, Eye, EyeOff, LayoutDashboard, LogOut, Menu, Plus, ReceiptText, ShieldCheck, X } from 'lucide-react'
import { api, ApiError, setCsrfToken } from './lib/api'
import { monthISO } from './lib/format'
import type { Session, Transaction } from './lib/types'
import { Brand, ErrorMessage, Loading } from './components/Shared'
import Dashboard from './components/Dashboard'
import Reports from './components/Reports'
import Transactions from './components/Transactions'
import TransactionModal from './components/TransactionModal'

type Page = 'dashboard' | 'transactions' | 'reports'
const navigation = [
  { id: 'dashboard' as const, label: 'Dashboard', icon: LayoutDashboard },
  { id: 'transactions' as const, label: 'Transactions', icon: ReceiptText },
  { id: 'reports' as const, label: 'Reports', icon: ChartNoAxesCombined },
]

function LoginScreen({ onSignedIn }: { onSignedIn: (session: Session) => void }) {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [visible, setVisible] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  async function submit(e: FormEvent) {
    e.preventDefault(); setError(''); setBusy(true)
    try { const session = await api.login(email, password); onSignedIn(session) }
    catch (err) { setError(err instanceof Error ? err.message : 'Sign-in failed.') }
    finally { setBusy(false) }
  }
  return <div className="grid min-h-dvh bg-canvas lg:grid-cols-[1fr_1fr]">
    <aside className="relative hidden overflow-hidden bg-navy p-14 text-white lg:flex lg:flex-col lg:justify-between">
      <div className="absolute -right-48 -top-40 h-[540px] w-[540px] rounded-full border border-white/10"/>
      <div className="absolute -right-20 -top-10 h-[340px] w-[340px] rounded-full border border-white/10"/>
      <div className="relative"><Brand light/></div>
      <div className="relative max-w-[540px]"><div className="mb-9 flex h-16 w-16 items-center justify-center rounded-3xl border border-white/15 bg-white/10"><ShieldCheck size={31} className="text-lavender"/></div>
        <div className="mb-5 text-xs font-bold uppercase tracking-[.2em] text-lavender">A CLEARER VIEW OF HOME FINANCES</div>
        <h1 className="text-[clamp(2.8rem,4.5vw,4.6rem)] font-extrabold leading-[1.12] tracking-[-.05em]">Every rupee,<br/><span className="text-lavender">beautifully</span><br/>accounted for.</h1>
        <p className="mt-7 max-w-md text-base leading-relaxed text-white/65">Keep household income, expenses and your remaining balance together in one quiet, organized space.</p>
      </div>
      <div className="relative border-t border-white/15 pt-5 text-xs text-white/50">Private by design. Simple by nature.</div>
    </aside>
    <main className="flex min-h-dvh items-center justify-center px-5 py-12 sm:px-10 lg:px-16">
      <div className="w-full max-w-[440px]"><div className="mb-11 lg:hidden"><Brand /></div>
        <div className="mb-9"><div className="eyebrow">WELCOME BACK</div><h2 className="mt-2 text-[32px] font-extrabold tracking-tight">Sign in to GharKhata</h2><p className="mt-2 text-sm text-muted">Your household finances, all in one place.</p></div>
        <form onSubmit={submit} className="space-y-5"><div><label htmlFor="login-email" className="field-label">Email address</label><input id="login-email" className="field !py-3.5" type="email" autoComplete="username" autoFocus required placeholder="you@example.com" value={email} onChange={e => setEmail(e.target.value)}/></div>
          <div><label htmlFor="login-password" className="field-label">Password</label><div className="relative"><input id="login-password" className="field !py-3.5 pr-12" type={visible ? 'text' : 'password'} autoComplete="current-password" required placeholder="Enter your password" value={password} onChange={e => setPassword(e.target.value)}/>
            <button type="button" className="icon-btn absolute right-2 top-1/2 -translate-y-1/2" aria-label={visible ? 'Hide password' : 'Show password'} onClick={() => setVisible(v => !v)}>{visible ? <EyeOff size={18}/> : <Eye size={18}/>}</button></div></div>
          {error && <ErrorMessage message={error}/>}<button className="primary-btn w-full !py-3.5" disabled={busy} type="submit">{busy ? 'Signing in…' : 'Sign in securely'}</button>
        </form><div className="mt-8 flex items-center justify-center gap-2 text-xs text-muted"><ShieldCheck size={15} className="text-indigo"/> Your records are private and protected.</div>
      </div>
    </main>
  </div>
}

function Workspace({ session, onSignOut }: { session: Session; onSignOut: () => void }) {
  const [page, setPage] = useState<Page>('dashboard')
  const [month, setMonth] = useState(monthISO())
  const [refreshVersion, setRefreshVersion] = useState(0)
  const [modalOpen, setModalOpen] = useState(false)
  const [edit, setEdit] = useState<Transaction | null>(null)
  const [mobileMenu, setMobileMenu] = useState(false)
  const [loggingOut, setLoggingOut] = useState(false)
  const [logoutError, setLogoutError] = useState('')
  const closeModal = useCallback(() => { setModalOpen(false); setEdit(null) }, [])
  function openAdd() { setEdit(null); setModalOpen(true) }
  function openEdit(transaction: Transaction) { setEdit(transaction); setModalOpen(true) }
  function saved() { closeModal(); setRefreshVersion(n => n + 1) }
  function navigate(destination: Page) { setPage(destination); setMobileMenu(false) }
  async function logout() {
    setLoggingOut(true); setLogoutError('')
    try { await api.logout(); onSignOut() }
    catch (err) { setLogoutError(err instanceof Error ? err.message : 'Unable to sign out.') }
    finally { setLoggingOut(false) }
  }
  const current = navigation.find(n => n.id === page)!
  return <div className="min-h-dvh bg-canvas lg:flex">
    <aside className="sticky top-0 hidden h-dvh w-[256px] shrink-0 flex-col bg-navy px-5 py-7 text-white lg:flex">
      <div className="mb-12 px-3"><Brand light/></div>
      <div className="mb-3 px-4 text-[10px] font-bold uppercase tracking-[.2em] text-white/45">WORKSPACE</div>
      <nav className="space-y-1" aria-label="Main navigation">{navigation.map(item => <button key={item.id} onClick={() => navigate(item.id)} className={`flex w-full items-center gap-3 rounded-xl px-4 py-3.5 text-sm font-semibold transition ${page === item.id ? 'bg-white/15 text-white' : 'text-white/60 hover:bg-white/10 hover:text-white'}`} aria-current={page === item.id ? 'page' : undefined}><item.icon size={19}/>{item.label}</button>)}</nav>
      <div className="mt-auto"><div className="mb-4 rounded-2xl border border-white/10 bg-white/5 p-4"><div className="flex items-center gap-2 text-xs font-semibold text-white/80"><ShieldCheck size={16} className="text-lavender"/> Private household space</div><div className="mt-2 truncate text-[11px] text-white/45" title={session.email}>{session.email}</div></div>
        <button onClick={logout} disabled={loggingOut} className="flex w-full items-center gap-3 rounded-xl px-4 py-3 text-sm font-semibold text-white/65 transition hover:bg-white/10 hover:text-white"><LogOut size={18}/>{loggingOut ? 'Signing out…' : 'Sign out'}</button></div>
    </aside>
    <div className="min-w-0 flex-1">
      <header className="sticky top-0 z-20 border-b border-line bg-white/95 px-4 backdrop-blur-sm sm:px-8 lg:px-10">
        <div className="mx-auto flex h-[76px] max-w-[1440px] items-center justify-between gap-2">
          <div className="flex items-center gap-3"><button aria-label="Open navigation" className="icon-btn lg:hidden" onClick={() => setMobileMenu(v => !v)}>{mobileMenu ? <X size={21}/> : <Menu size={21}/>}</button>
            <div><h1 className="hidden text-base font-extrabold tracking-tight min-[400px]:block sm:text-xl">{current.label}</h1><p className="hidden text-xs text-muted sm:block">Welcome to your financial home</p></div></div>
          <div className="flex items-center gap-2 sm:gap-3">{page === 'dashboard' && <label className="flex items-center gap-2 rounded-xl border border-line bg-white px-2.5 py-2 text-muted sm:px-3"><CalendarDays size={17}/><span className="sr-only">Dashboard month</span><input type="month" aria-label="Dashboard month" className="w-[112px] bg-transparent text-xs font-bold text-navy outline-none sm:w-[145px] sm:text-sm" value={month} onChange={e => setMonth(e.target.value)} /></label>}
            <button onClick={openAdd} aria-label="Add transaction" className="flex h-10 w-10 items-center justify-center rounded-xl bg-indigo text-white transition hover:bg-[#4338CA] sm:h-auto sm:w-auto sm:gap-2 sm:px-4 sm:py-2.5"><Plus size={17}/><span className="hidden text-xs font-bold sm:inline">Quick add</span></button></div>
        </div>
        {mobileMenu && <nav className="mb-3 rounded-2xl border border-line bg-white p-2 shadow-card lg:hidden" aria-label="Mobile menu">{navigation.map(item => <button key={item.id} onClick={() => navigate(item.id)} className={`flex w-full items-center gap-3 rounded-xl px-3 py-3 text-left text-sm font-semibold ${page === item.id ? 'bg-canvas text-indigo' : 'text-muted'}`}><item.icon size={17}/>{item.label}</button>)}<button onClick={logout} className="flex w-full items-center gap-3 rounded-xl px-3 py-3 text-sm font-semibold text-muted"><LogOut size={17}/>Sign out</button></nav>}
      </header>
      <main className="mx-auto max-w-[1440px] px-4 pb-28 pt-7 sm:px-8 sm:pt-9 lg:px-10 lg:pb-12">
        {logoutError && <div className="mb-5"><ErrorMessage message={logoutError}/></div>}
        {page === 'dashboard' && <Dashboard month={month || monthISO()} refreshVersion={refreshVersion} onAdd={openAdd} onTransactions={() => navigate('transactions')}/>}
        {page === 'transactions' && <Transactions refreshVersion={refreshVersion} onAdd={openAdd} onEdit={openEdit}/>}
        {page === 'reports' && <Reports refreshVersion={refreshVersion}/>}
        <div className="pt-8 text-center text-[11px] text-muted/70">GharKhata · Simple finances, peaceful living.</div>
      </main>
    </div>
    <nav className="fixed bottom-0 left-0 right-0 z-30 flex justify-around border-t border-line bg-white/95 px-3 pb-[max(8px,env(safe-area-inset-bottom))] pt-2 backdrop-blur-md lg:hidden" aria-label="Bottom navigation">{navigation.map(item => <button key={item.id} onClick={() => navigate(item.id)} aria-current={page === item.id ? 'page' : undefined} className={`flex min-w-20 flex-col items-center gap-1 rounded-xl px-3 py-1.5 text-[10px] font-bold transition ${page === item.id ? 'text-indigo' : 'text-muted'}`}><item.icon size={21} strokeWidth={page === item.id ? 2.4 : 1.8}/>{item.label}</button>)}</nav>
    {modalOpen && <TransactionModal edit={edit} onClose={closeModal} onSaved={saved}/>}
  </div>
}

export default function App() {
  const [session, setSession] = useState<Session | null>(null)
  const [ready, setReady] = useState(false)
  const [startupError, setStartupError] = useState('')
  async function checkSession() {
    setStartupError('')
    try { const current = await api.me(); setCsrfToken(current.csrf_token); setSession(current) }
    catch (err) {
      if (err instanceof ApiError && err.status !== 401) setStartupError(err.message)
      setCsrfToken(null); setSession(null)
    } finally { setReady(true) }
  }
  useEffect(() => { void checkSession() }, [])
  useEffect(() => {
    const onExpired = () => { setCsrfToken(null); setSession(null) }
    window.addEventListener('gharkhata:session-expired', onExpired)
    return () => window.removeEventListener('gharkhata:session-expired', onExpired)
  }, [])
  if (!ready) return <div className="flex min-h-dvh items-center justify-center bg-canvas"><Loading/></div>
  if (startupError) return <div className="mx-auto max-w-md px-5 py-20"><ErrorMessage message={startupError} retry={() => { setReady(false); void checkSession() }}/></div>
  if (!session) return <LoginScreen onSignedIn={setSession}/>
  return <Workspace session={session} onSignOut={() => { setSession(null); setCsrfToken(null) }}/>
}
