import { useState } from 'react'
import { NavLink, Outlet, useLocation } from 'react-router-dom'
import {
  Bot,
  CirclePlus,
  FileBarChart,
  LayoutDashboard,
  Menu,
  Moon,
  ReceiptText,
  Settings,
  Sun,
  X,
} from 'lucide-react'
import { useApp } from '../context/AppContext'
import { ModeBanner } from './ModeBanner'
import { useTheme } from '../context/ThemeContext'

const NAV = [
  { to: '/', label: 'Overview', icon: LayoutDashboard, end: true },
  { to: '/transactions', label: 'Transactions', icon: ReceiptText, end: false },
  { to: '/new-payment', label: 'New payment', icon: CirclePlus, end: false },
  { to: '/assistant', label: 'AI assistant', icon: Bot, end: false },
  { to: '/reports', label: 'Reports', icon: FileBarChart, end: false },
  { to: '/settings', label: 'Settings', icon: Settings, end: false },
]

function Logo() {
  return (
    <div className="flex items-center gap-2.5">
      <span className="grid h-9 w-9 place-items-center rounded-lg bg-accent font-bold text-white shadow-[0_6px_18px_-6px_rgb(124_92_255/0.9)]">
        P
      </span>
      <div className="leading-tight">
        <p className="text-[15px] font-semibold text-ink">PayPilot AI</p>
        <p className="text-[10px] uppercase tracking-[0.14em] text-faint">Payment ops</p>
      </div>
    </div>
  )
}

function NavList({ onNavigate }: { onNavigate?: () => void }) {
  return (
    <nav className="flex flex-1 flex-col gap-1 px-3" aria-label="Primary">
      {NAV.map((item) => (
        <NavLink
          key={item.to}
          to={item.to}
          end={item.end}
          onClick={onNavigate}
          className={({ isActive }) =>
            `group flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition ${
              isActive
                ? 'bg-accent/14 text-ink shadow-[inset_2px_0_0_0_var(--color-accent)]'
                : 'text-muted hover:bg-navy-800/10 hover:text-ink'
            }`
          }
        >
          <item.icon size={17} aria-hidden="true" />
          {item.label}
        </NavLink>
      ))}

      <div className="mt-auto space-y-3 px-3 pb-3 pt-6">
        <div className="rounded-lg border border-navy-700/15 bg-navy-850 p-3">
          <div className="flex items-center gap-3">
            <div className="grid h-8 w-8 place-items-center rounded-lg bg-accent/20 text-accent font-semibold text-sm">
              P
            </div>
            <div className="min-w-0 flex-1">
              <p className="text-sm font-medium text-ink truncate">PayPilot AI</p>
              <p className="text-[11px] text-faint truncate">ADMIN</p>
            </div>
            <span className="h-2 w-2 rounded-full bg-success" title="Active session" />
          </div>
        </div>
      </div>
    </nav>
  )
}

function ModeChip() {
  const { config, health } = useApp()
  if (!config) return null
  const sandbox = config.paypal.mode === 'sandbox'
  const live = config.paypal.mode === 'live'
  return (
    <div className="hidden items-center gap-2 sm:flex">
      <span
        className={`tag ${
          live
            ? 'border border-danger/35 bg-danger/12 text-danger'
            : sandbox
            ? 'border border-success/30 bg-success/12 text-success'
            : 'border border-warning/35 bg-warning/12 text-warning'
        }`}
      >
        <span
          className={`h-1.5 w-1.5 rounded-full ${live ? 'bg-danger' : sandbox ? 'bg-success' : 'bg-warning'}`}
          aria-hidden="true"
        />
        {live ? 'LIVE' : sandbox ? 'SANDBOX' : 'DEMO'}
      </span>
      <span className="hidden text-[11px] text-faint md:inline">
        AI: <span className="text-muted">{config.ai.model}</span>
      </span>
      {health?.database === 'connected' ? (
        <span className="hidden h-1.5 w-1.5 rounded-full bg-success lg:inline" title="Database connected" />
      ) : null}
    </div>
  )
}

export function Layout() {
  const [open, setOpen] = useState(false)
  const location = useLocation()
  const { theme, toggleTheme } = useTheme()

  return (
    <div className="min-h-screen bg-navy-950">
      {/* Desktop sidebar */}
      <aside className="fixed inset-y-0 left-0 z-40 hidden w-60 flex-col border-r border-navy-700/15 bg-navy-900 lg:flex">
        <div className="flex h-16 items-center border-b border-navy-700/15 px-5">
          <Logo />
        </div>
        <div className="flex flex-1 flex-col overflow-y-auto pt-5">
          <NavList />
        </div>
      </aside>

      {/* Mobile drawer */}
      {open ? (
        <div className="fixed inset-0 z-50 lg:hidden">
          <button
            type="button"
            className="absolute inset-0 bg-navy-950/65 backdrop-blur-sm"
            onClick={() => setOpen(false)}
            aria-label="Close navigation"
          />
          <div className="absolute inset-y-0 left-0 flex w-64 flex-col border-r border-navy-700/15 bg-navy-900">
            <div className="flex h-16 items-center justify-between border-b border-navy-700/15 px-5">
              <Logo />
              <button
                type="button"
                className="rounded-md p-1.5 text-muted hover:bg-navy-800/10 hover:text-ink"
                onClick={() => setOpen(false)}
                aria-label="Close navigation"
              >
                <X size={18} aria-hidden="true" />
              </button>
            </div>
            <div className="flex flex-1 flex-col overflow-y-auto pt-5">
              <NavList onNavigate={() => setOpen(false)} />
            </div>
          </div>
        </div>
      ) : null}

      <div className="lg:pl-60">
        <header className="sticky top-0 z-30 border-b border-navy-700/15 bg-navy-950/88 backdrop-blur-md">
          <ModeBanner />
          <div className="mx-auto flex h-14 max-w-[1400px] items-center gap-3 px-4 sm:px-6">
            <button
              type="button"
              className="rounded-md p-2 text-muted hover:bg-navy-800/10 hover:text-ink lg:hidden"
              onClick={() => setOpen(true)}
              aria-label="Open navigation"
            >
              <Menu size={18} aria-hidden="true" />
            </button>
            <p className="truncate text-sm text-muted">
              {NAV.find((item) =>
                item.end ? location.pathname === item.to : location.pathname.startsWith(item.to),
              )?.label ?? 'Overview'}
            </p>
            <div className="ml-auto flex items-center gap-3">
              <ModeChip />
              <button
                type="button"
                className="rounded-md p-2 text-muted hover:bg-navy-800/10 hover:text-ink transition-colors"
                onClick={toggleTheme}
                aria-label={theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'}
                title={theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'}
              >
                {theme === 'dark' ? <Sun size={18} aria-hidden="true" /> : <Moon size={18} aria-hidden="true" />}
              </button>
              <NavLink to="/new-payment" className="btn btn-primary !px-3 !py-2 text-xs sm:!px-4 sm:text-sm">
                <CirclePlus size={15} aria-hidden="true" />
                <span className="hidden sm:inline">New payment</span>
                <span className="sm:hidden">New</span>
              </NavLink>
            </div>
          </div>
        </header>

        <main className="mx-auto w-full max-w-[1400px] px-4 py-6 sm:px-6 sm:py-8">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
