import type { NewsItem } from './news'

/** URL of the standalone EnerX AI service (api.py). Leave unset to use the built-in simulation. */
export const AI_API_URL = (process.env.NEXT_PUBLIC_AI_API_URL ?? '').replace(/\/$/, '')

export interface AiDay {
  date: string
  temperature_c: number
  irradiance_wh_m2: number
  kwh: number
  kwh_low: number
  kwh_high: number
  revenue_dt: number
  revenue_usdc?: number
  dividend_per_token_dt: number
  dividend_per_token_usdc?: number
}

export interface AiReport {
  capacity_kw: number
  assumptions: { tariff_dt_per_kwh: number; n_tokens: number; fx?: { rate: number; status: string } }
  days: AiDay[]
  totals: { kwh: number; revenue_dt: number; revenue_usdc?: number }
  warnings?: string[]
  report_hash: string
}

interface AiNewsItem {
  title: string
  source: string
  url: string
  date: string | null
  summary: string
}

async function aiGet<T>(path: string, timeoutMs: number): Promise<T> {
  if (!AI_API_URL) throw new Error('NEXT_PUBLIC_AI_API_URL not set')
  const res = await fetch(`${AI_API_URL}${path}`, { cache: 'no-store', signal: AbortSignal.timeout(timeoutMs) })
  if (!res.ok) throw new Error(`AI service ${res.status}`)
  return (await res.json()) as T
}

export function fetchAiForecast(p: { lat: number; lon: number; capacityKw: number; days: number; nTokens: number }) {
  const q = new URLSearchParams({
    lat: String(p.lat),
    lon: String(p.lon),
    capacity_kw: String(p.capacityKw),
    days: String(p.days),
    n_tokens: String(p.nTokens),
  })
  return aiGet<AiReport>(`/forecast?${q}`, 45_000)
}

export async function fetchAiNews(): Promise<NewsItem[]> {
  const data = await aiGet<{ items: AiNewsItem[] }>('/news', 10_000)
  return data.items.map((n, i) => ({
    id: `ai-${i}-${n.url}`,
    title: n.title,
    source: n.source || 'News',
    url: n.url,
    summary: n.summary || undefined,
    publishedAt: n.date ? new Date(n.date).toISOString() : null,
  }))
}
