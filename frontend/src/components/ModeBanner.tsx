import { Link } from 'react-router-dom'
import { TriangleAlert } from 'lucide-react'
import type { ReactNode } from 'react'
import { useApp } from '../context/AppContext'

/** Global, unmissable banner when the app is running without PayPal credentials
 * or is showing clearly-labelled sample data. */
export function ModeBanner() {
  const { config, demoMode, loading, error } = useApp()

  if (loading) return null

  if (error) {
    return (
      <div className="border-b border-navy-700/30 bg-navy-800/10 px-4 py-2.5 text-xs font-medium text-danger sm:px-6">
        <div className="mx-auto flex max-w-[1400px] items-center gap-2">
          <TriangleAlert size={14} aria-hidden="true" />
          Backend unreachable — {error}
        </div>
      </div>
    )
  }

  const messages: { key: string; tone: string; text: ReactNode }[] = []

  if (demoMode) {
    messages.push({
      key: 'demo-mode',
      tone: 'border-warning/30 bg-warning/10 text-warning',
      text: (
        <>
          <strong className="font-semibold">DEMO MODE</strong> — PayPal credentials are not
          configured, so checkout results are simulated locally.{' '}
          <span className="opacity-80">No Sandbox transaction has occurred.</span>{' '}
          <Link to="/settings" className="underline underline-offset-2 hover:opacity-100">
            Set up PayPal →
          </Link>
        </>
      ),
    })
  } else if (config?.paypal.mode === 'live') {
    messages.push({
      key: 'live-mode',
      tone: 'border-danger/40 bg-danger/12 text-danger',
      text: (
        <>
          <strong className="font-semibold">LIVE PAYMENTS</strong> — real money will move. This is
          not the intended configuration for the hackathon demo.
        </>
      ),
    })
  }

  if (config?.demo_data_seeded) {
    messages.push({
      key: 'demo-data',
      tone: 'border-navy-700/15 bg-navy-800/10 text-muted',
      text: (
        <>
          <span className="tag border border-navy-700/20 bg-navy-800/10 text-[10px] text-muted">DEMO DATA</span>{' '}
          Sample rows are included and are labelled <code className="font-mono">DEMO</code> everywhere
          they appear. They are not real PayPal transactions.
        </>
      ),
    })
  }

  if (messages.length === 0) return null

  return (
    <div className="border-b border-navy-700/15">
      <div className="mx-auto max-w-[1400px] space-y-1 px-4 py-2 sm:px-6">
        {messages.map((message) => (
          <p
            key={message.key}
            className={`flex flex-wrap items-center gap-x-2 gap-y-1 rounded-md border px-3 py-1.5 text-xs leading-relaxed ${message.tone}`}
          >
            {message.text}
          </p>
        ))}
      </div>
    </div>
  )
}
