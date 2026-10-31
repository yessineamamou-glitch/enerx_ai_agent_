import { NextResponse } from 'next/server'
import { FALLBACK_NEWS, type NewsItem, type NewsResponse } from '@/lib/enerx/news'

// Runs on the Next.js server: no database, no FastAPI needed.
export const dynamic = 'force-dynamic'

// Step 1 of the news agent: look for energy news that matter for Tunisian solar.
const QUERIES = [
  'Tunisia solar energy',
  'STEG Tunisie photovoltaïque',
  'Tunisia electricity grid renewable',
]
const MAX_ITEMS = 6
const CACHE_MS = 15 * 60 * 1000

let cache: { at: number; body: NewsResponse } | null = null

const decode = (s: string) =>
  s
    .replace(/<!\[CDATA\[([\s\S]*?)\]\]>/g, '$1')
    .replace(/&amp;/g, '&')
    .replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>')
    .replace(/&quot;/g, '"')
    .replace(/&#39;|&apos;/g, "'")
    .trim()

const tag = (xml: string, name: string) => {
  const m = xml.match(new RegExp(`<${name}[^>]*>([\\s\\S]*?)</${name}>`))
  return m ? decode(m[1]) : ''
}

export function parseRss(xml: string): NewsItem[] {
  const items = xml.match(/<item>[\s\S]*?<\/item>/g) ?? []
  return items.flatMap((raw, i) => {
    const full = tag(raw, 'title')
    const source = tag(raw, 'source')
    const title = source && full.endsWith(` - ${source}`) ? full.slice(0, -(source.length + 3)) : full
    const url = tag(raw, 'link')
    const date = new Date(tag(raw, 'pubDate'))
    if (!title || !url || Number.isNaN(date.getTime())) return []
    return [{ id: `${date.getTime()}-${i}`, title, source: source || 'News', url, publishedAt: date.toISOString() }]
  })
}

async function fetchQuery(q: string): Promise<NewsItem[]> {
  const url = `https://news.google.com/rss/search?q=${encodeURIComponent(q + ' when:14d')}&hl=en&gl=TN&ceid=TN:en`
  const res = await fetch(url, { signal: AbortSignal.timeout(6000), cache: 'no-store' })
  if (!res.ok) throw new Error(`RSS ${res.status}`)
  return parseRss(await res.text())
}

async function loadLive(): Promise<NewsResponse> {
  // Optional: plug YOUR OWN news agent. It must return NewsItem[] (same shape as lib/enerx/news.ts).
  const agentUrl = process.env.NEWS_AGENT_URL
  if (agentUrl) {
    const res = await fetch(agentUrl, { signal: AbortSignal.timeout(8000), cache: 'no-store' })
    if (!res.ok) throw new Error(`agent ${res.status}`)
    const data = (await res.json()) as NewsItem[] | { items: NewsItem[] }
    const items = Array.isArray(data) ? data : data.items
    return { items: items.slice(0, MAX_ITEMS), origin: 'agent', fetchedAt: new Date().toISOString() }
  }

  const results = await Promise.allSettled(QUERIES.map(fetchQuery))
  const seen = new Set<string>()
  const items = results
    .flatMap((r) => (r.status === 'fulfilled' ? r.value : []))
    .filter((n) => {
      const key = n.title.toLowerCase().slice(0, 60)
      if (seen.has(key)) return false
      seen.add(key)
      return true
    })
    .sort((a, b) => +new Date(b.publishedAt ?? 0) - +new Date(a.publishedAt ?? 0))
    .slice(0, MAX_ITEMS)
  if (items.length === 0) throw new Error('no news')
  return { items, origin: 'live', fetchedAt: new Date().toISOString() }
}

export async function GET() {
  if (cache && Date.now() - cache.at < CACHE_MS) return NextResponse.json(cache.body)
  try {
    const body = await loadLive()
    cache = { at: Date.now(), body }
    return NextResponse.json(body)
  } catch {
    return NextResponse.json({ items: FALLBACK_NEWS, origin: 'fallback', fetchedAt: new Date().toISOString() } satisfies NewsResponse)
  }
}
