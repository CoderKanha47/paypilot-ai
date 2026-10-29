import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import { api, errorMessage } from '../lib/api'
import type { AppConfig, HealthResponse } from '../lib/types'

interface AppContextValue {
  config: AppConfig | null
  health: HealthResponse | null
  loading: boolean
  error: string | null
  reload: () => void
  /** True when PayPal credentials are absent (labelled demo mode). */
  demoMode: boolean
  /** True when clearly-labelled demo rows exist in the database. */
  hasDemoData: boolean
}

const AppContext = createContext<AppContextValue | null>(null)

export function AppProvider({ children }: { children: ReactNode }) {
  const [config, setConfig] = useState<AppConfig | null>(null)
  const [health, setHealth] = useState<HealthResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [nonce, setNonce] = useState(0)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(null)

    Promise.all([api.get<AppConfig>('/api/config'), api.get<HealthResponse>('/api/health')])
      .then(([nextConfig, nextHealth]) => {
        if (cancelled) return
        setConfig(nextConfig)
        setHealth(nextHealth)
        setLoading(false)
      })
      .catch((cause) => {
        if (cancelled) return
        setError(errorMessage(cause))
        setLoading(false)
      })

    return () => {
      cancelled = true
    }
  }, [nonce])

  const value = useMemo<AppContextValue>(
    () => ({
      config,
      health,
      loading,
      error,
      reload: () => setNonce((value) => value + 1),
      demoMode: config ? !config.paypal.configured : false,
      hasDemoData: config?.demo_data_seeded ?? false,
    }),
    [config, health, loading, error],
  )

  return <AppContext.Provider value={value}>{children}</AppContext.Provider>
}

export function useApp(): AppContextValue {
  const value = useContext(AppContext)
  if (!value) throw new Error('useApp must be used inside <AppProvider>')
  return value
}
