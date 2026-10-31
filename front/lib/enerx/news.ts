export interface NewsItem {
  id: string
  title: string
  source: string
  url: string
  summary?: string
  publishedAt: string | null // ISO date
}

export interface NewsResponse {
  items: NewsItem[]
  /** 'model' = AI service (etape 1 collector), 'live' = Google News RSS, 'agent' = custom agent, 'fallback' = offline demo data */
  origin: 'model' | 'live' | 'agent' | 'fallback'
  fetchedAt: string
}

/** Shown only if no live news can be fetched (no internet during the demo, etc.). */
export const FALLBACK_NEWS: NewsItem[] = [
  {
    id: 'f1',
    title: 'Tunisia accelerates rooftop solar rollout to ease summer peak demand',
    source: 'Demo data',
    url: 'https://news.google.com/search?q=Tunisia%20solar',
    publishedAt: new Date(Date.now() - 3600_000 * 5).toISOString(),
  },
  {
    id: 'f2',
    title: 'STEG reviews net-metering rules for residential photovoltaic producers',
    source: 'Demo data',
    url: 'https://news.google.com/search?q=STEG%20photovolta%C3%AFque',
    publishedAt: new Date(Date.now() - 3600_000 * 26).toISOString(),
  },
  {
    id: 'f3',
    title: 'Heatwave forecast across southern Tunisia: higher irradiance, higher grid load',
    source: 'Demo data',
    url: 'https://news.google.com/search?q=Tunisia%20electricity',
    publishedAt: new Date(Date.now() - 3600_000 * 50).toISOString(),
  },
]
