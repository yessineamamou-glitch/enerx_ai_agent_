export const API_BASE_URL = (process.env.NEXT_PUBLIC_API_BASE_URL ?? 'http://localhost:8000').replace(/\/$/, '')

const wait = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms))

export class ApiError extends Error {
  status: number

  constructor(message: string, status: number) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

export async function apiRequest<T>(
  endpoint: string,
  payload?: unknown,
  _mockResponse?: () => unknown,
  _latencyMs = 0,
): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${endpoint}`, {
    method: payload === undefined ? 'GET' : 'POST',
    headers: payload === undefined ? undefined : { 'Content-Type': 'application/json' },
    body: payload === undefined ? undefined : JSON.stringify(payload),
    cache: 'no-store',
  })

  if (!response.ok) {
    let message = `API request failed with status ${response.status}`
    try {
      const error = (await response.json()) as { detail?: string | Array<{ msg?: string }> }
      if (typeof error.detail === 'string') message = error.detail
      if (Array.isArray(error.detail)) message = error.detail.map((item) => item.msg ?? 'Invalid request').join(', ')
    } catch {
      const text = await response.text()
      if (text) message = text
    }
    throw new ApiError(message, response.status)
  }

  if (response.status === 204) return undefined as T
  return (await response.json()) as T
}

export async function apiDelete(endpoint: string): Promise<void> {
  const response = await fetch(`${API_BASE_URL}${endpoint}`, {
    method: 'DELETE',
    cache: 'no-store',
  })
  if (!response.ok) {
    let message = `API request failed with status ${response.status}`
    try {
      const error = (await response.json()) as { detail?: string }
      if (error.detail) message = error.detail
    } catch {
      // Keep the HTTP status when the API does not return JSON.
    }
    throw new ApiError(message, response.status)
  }
}

export const sleep = wait
