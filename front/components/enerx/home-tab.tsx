import { Activity, ArrowRight, BrainCircuit, Building2, Coins, ShieldCheck, Sun, Timer, TrendingUp } from 'lucide-react'
import type { ProductionEvent, Project, TabId } from '@/lib/enerx/types'
import { INVESTOR_ALLOCATION, collectedFunding, formatNumber, formatUSD } from '@/lib/enerx/utils'
import { cn } from '@/lib/utils'

interface HomeTabProps {
  projects: Project[]
  history: ProductionEvent[]
  onNavigate: (tab: TabId) => void
}

const QUICK_ACTIONS: {
  tab: TabId
  title: string
  description: string
  icon: typeof TrendingUp
  accent: string
}[] = [
  {
    tab: 'invest',
    title: 'Invest in rooftops',
    description: 'Buy fractional HTS tokens in primary campaigns or trade peer-to-peer.',
    icon: TrendingUp,
    accent: 'text-solar ring-solar/40 bg-solar/10',
  },
  {
    tab: 'owner',
    title: 'Tokenize your array',
    description: 'Deploy a 100-unit HTS token and stream STEG revenue to holders.',
    icon: Building2,
    accent: 'text-azure ring-azure/40 bg-azure/10',
  },
  {
    tab: 'ai',
    title: 'Forecast returns',
    description: 'AI irradiance and cloud-cover models across four Tunisian regions.',
    icon: BrainCircuit,
    accent: 'text-ledger ring-ledger/40 bg-ledger/10',
  },
]

const RIBBON = [
  { icon: ShieldCheck, label: 'GUARDIAN HCS-721 AUDITED', color: 'text-ledger' },
  { icon: Timer, label: 'SUB-SECOND FINALITY: 0.8S', color: 'text-azure' },
  { icon: Activity, label: 'LIVE STEG INJECTION: 18.4 MW', color: 'text-solar' },
]

export function HomeTab({ projects, history, onNavigate }: HomeTabProps) {
  const totalRaised = projects.reduce((sum, p) => sum + collectedFunding(p), 0)
  const liveCampaigns = projects.filter((p) => p.availableTokens > 0).length
  const tokensSold = projects.reduce((sum, p) => sum + (INVESTOR_ALLOCATION - p.availableTokens), 0)
  const distributed = history.reduce((sum, e) => sum + Number(e.revenue), 0)

  const stats = [
    { label: 'Capital raised', value: formatUSD(totalRaised, 0), icon: Coins },
    { label: 'Live campaigns', value: `${liveCampaigns} / ${projects.length}`, icon: Sun },
    { label: 'Investor tokens sold', value: formatNumber(tokensSold), icon: TrendingUp },
    { label: 'Revenue distributed', value: formatUSD(distributed), icon: Activity },
  ]

  return (
    <>
      <section className="bg-[url('/tunisia-rooftops.png')] bg-cover bg-center bg-no-repeat relative">
        <div className="absolute inset-0 bg-gradient-to-b from-slate-950/90 via-slate-900/75 to-slate-950" aria-hidden />
        <div className="relative mx-auto flex min-h-[calc(100dvh-4rem)] max-w-7xl flex-col px-4 pt-16 pb-8 md:px-6 md:pt-24">
          <div className="max-w-3xl">
            <p className="inline-flex items-center gap-2 rounded-full border border-azure/40 bg-slate-950/60 px-3 py-1 font-mono text-[11px] uppercase tracking-[0.2em] text-azure backdrop-blur">
              <span className="size-1.5 rounded-full bg-azure" aria-hidden />
              Real-world asset tokenization · Tunisia
            </p>
            <h1 className="mt-6 text-balance text-4xl font-bold leading-[1.05] tracking-tight text-white sm:text-5xl md:text-6xl lg:text-7xl">
              Empowering Clean Energy via <span className="text-solar drop-shadow-[0_0_24px_rgba(255,102,34,0.5)]">Hedera RWA</span>{' '}
              &amp; <span className="text-azure drop-shadow-[0_0_24px_rgba(34,211,238,0.5)]">AI</span>
            </h1>
            <p className="mt-6 max-w-2xl text-pretty text-base leading-relaxed text-slate-300 md:text-lg">
              EnerX tokenizes residential photovoltaic installations across Tunisian coastal villages, letting anyone
              co-own rooftop solar that relieves peak-demand deficits on the STEG grid — with every kilowatt-hour and
              payout settled on Hedera.
            </p>
            <div className="mt-8 flex flex-wrap gap-3">
              <button
                type="button"
                onClick={() => onNavigate('invest')}
                className="inline-flex items-center gap-2 rounded-lg bg-solar px-5 py-3 text-sm font-semibold text-slate-950 shadow-[0_0_30px_-4px_rgba(255,102,34,0.7)] transition hover:brightness-110"
              >
                Explore campaigns <ArrowRight className="size-4" aria-hidden />
              </button>
              <button
                type="button"
                onClick={() => onNavigate('owner')}
                className="inline-flex items-center gap-2 rounded-lg border border-white/20 bg-slate-950/50 px-5 py-3 text-sm font-semibold text-white backdrop-blur transition hover:border-azure/60 hover:text-azure"
              >
                Tokenize a rooftop
              </button>
            </div>
          </div>

          <div className="mt-12 grid gap-4 md:grid-cols-3">
            {QUICK_ACTIONS.map(({ tab, title, description, icon: Icon, accent }) => (
              <button
                key={tab}
                type="button"
                onClick={() => onNavigate(tab)}
                className="group rounded-2xl border border-white/10 bg-slate-950/60 p-5 text-left backdrop-blur-md transition hover:-translate-y-0.5 hover:border-white/25 hover:bg-slate-900/70"
              >
                <span className={cn('flex size-10 items-center justify-center rounded-lg ring-1', accent)}>
                  <Icon className="size-5" aria-hidden />
                </span>
                <span className="mt-4 flex items-center justify-between text-base font-semibold text-white">
                  {title}
                  <ArrowRight className="size-4 text-slate-500 transition group-hover:translate-x-1 group-hover:text-white" aria-hidden />
                </span>
                <span className="mt-1.5 block text-sm leading-relaxed text-slate-400">{description}</span>
              </button>
            ))}
          </div>

          <div className="mt-auto pt-10">
            <div className="flex flex-col divide-y divide-white/10 rounded-2xl border border-white/10 bg-slate-950/80 shadow-[0_0_60px_-20px_rgba(34,211,238,0.5)] backdrop-blur-xl md:flex-row md:divide-x md:divide-y-0">
              {RIBBON.map(({ icon: Icon, label, color }) => (
                <div key={label} className="flex flex-1 items-center gap-3 px-5 py-4">
                  <span className="relative flex size-2">
                    <span className={cn('absolute inline-flex size-full animate-ping rounded-full bg-current opacity-60', color)} />
                    <span className={cn('relative inline-flex size-2 rounded-full bg-current', color)} />
                  </span>
                  <Icon className={cn('size-4', color)} aria-hidden />
                  <span className="font-mono text-xs font-semibold tracking-wider text-slate-200">{label}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>

      <section className="enerx-grid-bg border-t border-white/5" aria-label="Platform snapshot">
        <div className="mx-auto grid max-w-7xl gap-4 px-4 py-14 sm:grid-cols-2 md:px-6 lg:grid-cols-4">
          {stats.map(({ label, value, icon: Icon }) => (
            <div key={label} className="rounded-2xl border border-white/10 bg-slate-900/70 p-5">
              <div className="flex items-center justify-between">
                <p className="font-mono text-[11px] uppercase tracking-wider text-slate-400">{label}</p>
                <Icon className="size-4 text-slate-500" aria-hidden />
              </div>
              <p className="mt-3 text-2xl font-semibold text-white">{value}</p>
            </div>
          ))}
        </div>
      </section>
    </>
  )
}
