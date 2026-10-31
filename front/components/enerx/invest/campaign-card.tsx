'use client'

import { Lock, MapPin, Minus, Plus } from 'lucide-react'
import { useState } from 'react'
import type { Profile, Project } from '@/lib/enerx/types'
import { INVESTOR_ALLOCATION, collectedFunding, formatUSD, tokenPrice } from '@/lib/enerx/utils'
import { cn } from '@/lib/utils'
import { Panel, ProgressBar, Spinner } from '../primitives'

interface CampaignCardProps {
  project: Project
  activeProfile: Profile
  verified: boolean
  isPending: boolean
  isBusy: boolean
  onBuy: (projectId: string, quantity: number) => void
  onOpenKyc: () => void
}

export function CampaignCard({ project, activeProfile, verified, isPending, isBusy, onBuy, onOpenKyc }: CampaignCardProps) {
  const [quantity, setQuantity] = useState(1)
  const price = tokenPrice(project)
  const collected = collectedFunding(project)
  const sold = INVESTOR_ALLOCATION - project.availableTokens
  const closed = project.availableTokens === 0
  const isOwnProject = project.ownerId === activeProfile.id
  const safeQuantity = Math.min(Math.max(1, quantity), Math.max(1, project.availableTokens))

  return (
    <Panel className={cn('flex flex-col p-5 transition', closed && 'opacity-80')}>
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <span className="rounded-md bg-azure/10 px-2 py-0.5 font-mono text-xs font-semibold text-azure ring-1 ring-azure/30">
              ${project.tokenSymbol}
            </span>
            <span className="font-mono text-[11px] text-slate-500">{project.hederaTokenId}</span>
          </div>
          <h4 className="mt-2 text-lg font-semibold text-white">{project.name}</h4>
          <p className="mt-1 flex items-center gap-1.5 text-xs text-slate-400">
            <MapPin className="size-3.5" aria-hidden /> {project.location} · {project.capacityKwp} kWp
          </p>
        </div>
        {closed ? (
          <span className="flex shrink-0 items-center gap-1.5 rounded-full border border-slate-600 bg-slate-800 px-3 py-1 font-mono text-[11px] font-bold tracking-wider text-slate-300">
            <Lock className="size-3" aria-hidden /> CLOSED
          </span>
        ) : (
          <span className="shrink-0 rounded-full border border-solar/40 bg-solar/10 px-3 py-1 font-mono text-[11px] font-bold tracking-wider text-solar">
            LIVE
          </span>
        )}
      </div>

      <p className="mt-3 text-sm leading-relaxed text-slate-400">{project.description}</p>

      <div className="mt-5">
        <div className="flex items-baseline justify-between text-sm">
          <span className="font-semibold text-white">{formatUSD(collected, 0)}</span>
          <span className="font-mono text-xs text-slate-500">of {formatUSD(project.targetFunding, 0)}</span>
        </div>
        <ProgressBar value={(collected / project.targetFunding) * 100} className="mt-2" barClassName={closed ? 'bg-ledger shadow-none' : undefined} />
      </div>

      <div className="mt-4" aria-label="Token supply breakdown">
        <div className="flex h-2.5 w-full overflow-hidden rounded-full bg-slate-800">
          <div className="h-full bg-azure/80" style={{ width: `${project.ownerRetained}%` }} />
          <div className="h-full bg-solar" style={{ width: `${sold}%` }} />
        </div>
        <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 font-mono text-[11px] text-slate-400">
          <span className="flex items-center gap-1.5">
            <span className="size-2 rounded-full bg-azure/80" aria-hidden /> Owner {project.ownerRetained}
          </span>
          <span className="flex items-center gap-1.5">
            <span className="size-2 rounded-full bg-solar" aria-hidden /> Sold {sold}
          </span>
          <span className="flex items-center gap-1.5">
            <span className="size-2 rounded-full bg-slate-700" aria-hidden /> Available {project.availableTokens}/{INVESTOR_ALLOCATION}
          </span>
        </div>
      </div>

      <div className="mt-5 flex flex-wrap items-end gap-3 border-t border-white/10 pt-4">
        <div>
          <p className="font-mono text-[11px] uppercase tracking-wider text-slate-500">Price / token</p>
          <p className="font-semibold text-white">{formatUSD(price)}</p>
        </div>

        {!closed && !isOwnProject && (
          <div className="ml-auto flex items-center gap-2">
            <div className="flex items-center rounded-lg border border-white/10 bg-slate-950/70">
              <button
                type="button"
                className="p-2 text-slate-400 hover:text-white disabled:opacity-40"
                onClick={() => setQuantity(Math.max(1, safeQuantity - 1))}
                disabled={safeQuantity <= 1}
                aria-label="Decrease quantity"
              >
                <Minus className="size-3.5" />
              </button>
              <label htmlFor={`qty-${project.id}`} className="sr-only">
                Token quantity
              </label>
              <input
                id={`qty-${project.id}`}
                type="number"
                inputMode="numeric"
                min={1}
                max={project.availableTokens}
                step={1}
                value={safeQuantity}
                onChange={(e) => setQuantity(Math.floor(Number(e.target.value) || 1))}
                className="w-12 bg-transparent text-center font-mono text-sm text-white outline-none [appearance:textfield] [&::-webkit-inner-spin-button]:appearance-none"
              />
              <button
                type="button"
                className="p-2 text-slate-400 hover:text-white disabled:opacity-40"
                onClick={() => setQuantity(Math.min(project.availableTokens, safeQuantity + 1))}
                disabled={safeQuantity >= project.availableTokens}
                aria-label="Increase quantity"
              >
                <Plus className="size-3.5" />
              </button>
            </div>
            {verified ? (
              <button
                type="button"
                onClick={() => onBuy(project.id, safeQuantity)}
                disabled={isBusy}
                className="inline-flex min-w-36 items-center justify-center gap-2 rounded-lg bg-solar px-4 py-2.5 text-sm font-semibold text-slate-950 shadow-[0_0_24px_-6px_rgba(255,102,34,0.8)] transition hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-60"
              >
                {isPending ? (
                  <>
                    <Spinner /> Submitting…
                  </>
                ) : (
                  `Buy · ${formatUSD(safeQuantity * price, 0)}`
                )}
              </button>
            ) : (
              <button
                type="button"
                onClick={onOpenKyc}
                className="rounded-lg border border-amber-400/50 px-4 py-2.5 text-sm font-semibold text-amber-300 transition hover:bg-amber-400/10"
              >
                Verify DID to buy
              </button>
            )}
          </div>
        )}
        {!closed && isOwnProject && (
          <p className="ml-auto font-mono text-xs text-slate-500">Your project · 30 tokens retained</p>
        )}
        {closed && <p className="ml-auto font-mono text-xs text-ledger">Fully funded · trade on secondary market</p>}
      </div>
    </Panel>
  )
}
