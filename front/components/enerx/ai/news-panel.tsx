'use client'

import { ExternalLink, Info, Newspaper, RefreshCw } from 'lucide-react'
import { useCallback, useEffect, useState } from 'react'
import { fetchAiNews } from '@/lib/enerx/ai-api'
import type { NewsResponse } from '@/lib/enerx/news'
import { cn } from '@/lib/utils'
import { Panel } from '../primitives'

function timeAgo(iso: string | null) {
  if (!iso) return 'recent'
  const hours = Math.max(0, Math.round((Date.now() - new Date(iso).getTime()) / 3600_000))
  if (hours < 1) return 'just now'
  if (hours < 24) return `${hours} h ago`
  return `${Math.round(hours / 24)} d ago`
}

export function NewsPanel() {
  const [data, setData] = useState<NewsResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [failed, setFailed] = useState(false)

  const load = useCallback(async () => {
    setLoading(true)
    setFailed(false)
    try {
      // 1) API Python (GET /news, articles collectes par l'agent)
      try {
        const items = await fetchAiNews()
        if (items.length > 0) {
          setData({ items, origin: 'model', fetchedAt: new Date().toISOString() })
          return
        }
      } catch (err) {
        console.warn('AI /news indisponible, repli sur le fichier local :', err)
      }

      // 2) secours : fichier statique public/articles_steg.json (cles francaises de l'agent)
      try {
        const res = await fetch('/articles_steg.json', { cache: 'no-store' })
        if (res.ok) {
          const raw = (await res.json()) as Array<Record<string, string>>
          const items = raw.map((art, i) => ({
            id: `file-${i}`,
            title: art.titre || art.title,
            summary: (art.texte_brut || art.summary || '').slice(0, 220) || undefined,
            url: art.url || '#',
            source: art.source || 'STEG Agent',
            publishedAt: art.date ? new Date(art.date).toISOString() : null,
          }))
          if (items.length > 0) {
            setData({ items, origin: 'fallback', fetchedAt: new Date().toISOString() })
            return
          }
        }
      } catch {
        /* pas de fichier local : on essaie Google News */
      }

      // 3) dernier recours : Google News via /api/news
      const res = await fetch('/api/news', { cache: 'no-store' })
      if (!res.ok) throw new Error(String(res.status))
      setData((await res.json()) as NewsResponse)
    } catch (err) {
      console.error('Erreur de chargement des news :', err)
      setFailed(true)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void load()
  }, [load])

  return (
    <Panel className="p-5">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="flex items-center gap-2 font-semibold text-white">
            <Newspaper className="size-5 text-azure" aria-hidden /> Energy news · Tunisia
          </h3>
          <p className="mt-1 flex items-start gap-1.5 text-xs text-slate-400">
            <Info className="mt-0.5 size-3.5 shrink-0 text-azure" aria-hidden />
            Information only. News are not included in the production forecast — you decide how to use them.
          </p>
        </div>
        <button
          type="button"
          onClick={() => void load()}
          disabled={loading}
          aria-label="Refresh news"
          className="rounded-lg border border-white/10 p-2 text-slate-400 transition hover:border-azure/50 hover:text-azure disabled:opacity-50"
        >
          <RefreshCw className={cn('size-4', loading && 'animate-spin')} aria-hidden />
        </button>
      </div>

      <div className="mt-4 grid gap-3 md:grid-cols-2 lg:grid-cols-3">
        {loading && !data
          ? Array.from({ length: 3 }, (_, i) => <div key={i} className="h-24 animate-pulse rounded-xl bg-white/5" />)
          : failed && !data
            ? <p className="text-sm text-slate-400 md:col-span-3">News unavailable right now. Try refreshing.</p>
            : data?.items.map((n) => (
                <a
                  key={n.id}
                  href={n.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="group flex flex-col justify-between gap-3 rounded-xl border border-white/10 bg-slate-950/60 p-4 transition hover:border-azure/40 hover:bg-slate-900/80"
                >
                  <div>
                    <p className="text-sm font-medium leading-snug text-slate-100">{n.title}</p>
                    {n.summary && <p className="mt-1.5 line-clamp-3 text-xs leading-relaxed text-slate-500">{n.summary}</p>}
                  </div>
                  <div className="flex items-center justify-between font-mono text-[11px] text-slate-500">
                    <span className="truncate">
                      {n.source} · {timeAgo(n.publishedAt)}
                    </span>
                    <ExternalLink className="size-3.5 shrink-0 text-slate-600 group-hover:text-azure" aria-hidden />
                  </div>
                </a>
              ))}
      </div>
      {data && (
        <p className="mt-3 font-mono text-[10px] uppercase tracking-wider text-slate-600">
          {data.origin === 'model' ? 'Source: AI service (/news)' : data.origin === 'fallback' ? 'Source: local file / offline data' : `Source: ${data.origin}`}
        </p>
      )}
    </Panel>
  )
}
