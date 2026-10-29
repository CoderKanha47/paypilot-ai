import { useCallback, useEffect, useRef, useState } from 'react'
import { errorMessage } from '../lib/api'

interface AsyncState<T> {
  data: T | null
  loading: boolean
  error: string | null
  reload: () => void
  setData: (value: T | null) => void
}

/** Small data-fetching hook with loading / error / reload semantics. */
export function useAsync<T>(fetcher: () => Promise<T>, deps: unknown[] = []): AsyncState<T> {
  const [data, setData] = useState<T | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [nonce, setNonce] = useState(0)
  const alive = useRef(true)

  const reload = useCallback(() => setNonce((value) => value + 1), [])

  useEffect(() => {
    alive.current = true
    let cancelled = false
    setLoading(true)
    setError(null)

    fetcher()
      .then((result) => {
        if (!cancelled) {
          setData(result)
          setLoading(false)
        }
      })
      .catch((cause) => {
        if (!cancelled) {
          setError(errorMessage(cause))
          setLoading(false)
        }
      })

    return () => {
      cancelled = true
      alive.current = false
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, nonce])

  return { data, loading, error, reload, setData }
}

/** Imperative action wrapper with pending + error state for forms/buttons. */
export function useAction<Args extends unknown[], R>(
  action: (...args: Args) => Promise<R>,
): {
  run: (...args: Args) => Promise<R | undefined>
  pending: boolean
  error: string | null
  reset: () => void
} {
  const [pending, setPending] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const run = useCallback(
    async (...args: Args) => {
      setPending(true)
      setError(null)
      try {
        return await action(...args)
      } catch (cause) {
        setError(errorMessage(cause))
        return undefined
      } finally {
        setPending(false)
      }
    },
    [action],
  )

  return { run, pending, error, reset: () => setError(null) }
}
