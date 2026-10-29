/** Typed fetch client for the PayPilot API with normalised error handling. */

import type { ApiErrorBody } from './types'

export class ApiError extends Error {
  readonly status: number
  readonly code: string
  readonly errors: string[]
  readonly detail: ApiErrorBody | null

  constructor(status: number, body: ApiErrorBody, fallback: string) {
    super(body.message || fallback)
    this.name = 'ApiError'
    this.status = status
    this.code = body.code || 'unknown_error'
    this.errors = body.errors ?? []
    this.detail = body
  }
}

const DEFAULT_TIMEOUT_MS = 30_000

interface RequestOptions extends Omit<RequestInit, 'body'> {
  body?: unknown
  timeoutMs?: number
}

export async function apiRequest<T>(
  path: string,
  { body, timeoutMs = DEFAULT_TIMEOUT_MS, headers, ...init }: RequestOptions = {},
): Promise<T> {
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), timeoutMs)

  let response: Response
  try {
    response = await fetch(path, {
      ...init,
      signal: controller.signal,
      headers: {
        Accept: 'application/json',
        ...(body !== undefined ? { 'Content-Type': 'application/json' } : {}),
        ...(headers as Record<string, string> | undefined),
      },
      body: body !== undefined ? JSON.stringify(body) : undefined,
    })
  } catch (cause) {
    clearTimeout(timer)
    const aborted = cause instanceof DOMException && cause.name === 'AbortError'
    throw new ApiError(
      0,
      {
        code: aborted ? 'timeout' : 'network_error',
        message: aborted
          ? `The request timed out after ${Math.round(timeoutMs / 1000)}s.`
          : 'Could not reach the PayPilot API. Is the backend running on port 8000?',
      },
      'Request failed',
    )
  }
  clearTimeout(timer)

  if (response.status === 204) return undefined as T

  const text = await response.text()
  let parsed: unknown = null
  if (text) {
    try {
      parsed = JSON.parse(text)
    } catch {
      if (!response.ok) {
        throw new ApiError(response.status, { code: 'invalid_response', message: text.slice(0, 300) }, 'Request failed')
      }
      throw new ApiError(response.status, { code: 'invalid_response', message: 'Server returned a non-JSON body.' }, 'Invalid response')
    }
  }

  if (!response.ok) {
    const detail =
      parsed && typeof parsed === 'object' && 'detail' in parsed
        ? ((parsed as { detail: unknown }).detail as ApiErrorBody)
        : null
    throw new ApiError(
      response.status,
      detail && typeof detail === 'object' ? detail : { code: 'http_error', message: `Request failed (HTTP ${response.status}).` },
      `Request failed (HTTP ${response.status})`,
    )
  }

  return parsed as T
}

export const api = {
  get: <T>(path: string, opts?: RequestOptions) => apiRequest<T>(path, { ...opts, method: 'GET' }),
  post: <T>(path: string, body?: unknown, opts?: RequestOptions) =>
    apiRequest<T>(path, { ...opts, method: 'POST', body: body ?? {} }),
  downloadUrl: (path: string) => path,
}

/** Human-friendly message for any thrown value. */
export function errorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.errors.length > 0) return `${error.message} — ${error.errors.join('; ')}`
    return error.message
  }
  if (error instanceof Error) return error.message
  return 'Something went wrong.'
}
