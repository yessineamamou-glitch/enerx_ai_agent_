'use client'

import { Cpu, Sun, Zap } from 'lucide-react'
import { useState } from 'react'
import type { ProductionEvent, Project } from '@/lib/enerx/types'
import { formatTimestamp, formatUSD } from '@/lib/enerx/utils'
import { cn } from '@/lib/utils'
import { Panel, Spinner, inputClass, labelClass } from '../primitives'

interface ProductionSimulatorProps {
  projects: Project[]
  history: ProductionEvent[]
  lastEvent: ProductionEvent | null
  isSimulating: boolean
  payload: { energy_kwh: string; revenue: string }
  onSimulate: (projectId: string) => void
}

export function ProductionSimulator({ projects, history, lastEvent, isSimulating, payload, onSimulate }: ProductionSimulatorProps) {
  const [selectedId, setSelectedId] = useState(projects[0]?.id ?? '')
  const selected = projects.find((p) => p.id === selectedId) ?? projects[0]
  const projectHistory = history.filter((e) => e.projectId === selected?.id)
  const breakdown = lastEvent && lastEvent.projectId === selected?.id ? lastEvent : projectHistory[0]

  const ownerTotal = breakdown?.distribution.filter((d) => d.holderId === selected?.ownerId).reduce((s, d) => s + Number(d.amount), 0) ?? 0
  const ownerPct = breakdown?.distribution.filter((d) => d.holderId === selected?.ownerId).reduce((s, d) => s + d.percent, 0) ?? 0
  const investorTotal = (Number(breakdown?.revenue ?? 0) - ownerTotal)

  if (!selected) {
    return (
      <Panel className="p-6 text-sm text-slate-400">Deploy a project to start simulating production data.</Panel>
    )
  }

  return (
    <section aria-labelledby="sim-heading">
      <Panel className="overflow-hidden">
        <div className="flex flex-col gap-4 border-b border-white/10 p-5 md:flex-row md:items-center md:justify-between md:p-6">
          <div>
            <h3 id="sim-heading" className="flex items-center gap-2 text-lg font-semibold text-white">
              <Cpu className="size-5 text-azure" aria-hidden /> Simulate Solar Production &amp; STEG Injection Data
            </h3>
            <p className="mt-1 text-sm text-slate-400">Oracle event → HSCS revenue-split contract → pro-rata payout to token holders.</p>
          </div>
          <div className="flex flex-col gap-2 sm:flex-row sm:items-end">
            <div className="sm:w-64">
              <label htmlFor="sim-project" className={labelClass}>
                Project
              </label>
              <select id="sim-project" value={selected.id} onChange={(e) => setSelectedId(e.target.value)} className={inputClass}>
                {projects.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name} (${p.tokenSymbol})
                  </option>
                ))}
              </select>
            </div>
            <button
              type="button"
              onClick={() => onSimulate(selected.id)}
              disabled={isSimulating}
              className="inline-flex items-center justify-center gap-2 rounded-lg bg-solar px-5 py-2.5 text-sm font-semibold text-slate-950 shadow-[0_0_24px_-6px_rgba(255,102,34,0.8)] transition hover:brightness-110 disabled:opacity-60"
            >
              {isSimulating ? (
                <>
                  <Spinner /> Executing contract…
                </>
              ) : (
                <>
                  <Zap className="size-4" aria-hidden /> Simulate injection
                </>
              )}
            </button>
          </div>
        </div>

        <div className="grid gap-px bg-white/5 lg:grid-cols-[20rem_1fr]">
          <div className="bg-slate-900/90 p-5 md:p-6">
            <p className={labelClass}>Event payload</p>
            <pre className="overflow-x-auto rounded-lg border border-white/10 bg-slate-950 p-4 font-mono text-xs leading-relaxed text-slate-300">
              {'{\n'}
              {'  '}
              <span className="text-azure">{'"project_id"'}</span>: <span className="text-amber-300">{`"${selected.hederaTokenId}"`}</span>,{'\n'}
              {'  '}
              <span className="text-azure">{'"energy_kwh"'}</span>: <span className="text-ledger">{`"${payload.energy_kwh}"`}</span>,{'\n'}
              {'  '}
              <span className="text-azure">{'"revenue"'}</span>: <span className="text-ledger">{`"${payload.revenue}"`}</span>
              {'\n}'}
            </pre>
            <div className="mt-4 grid grid-cols-2 gap-3">
              <div className="rounded-lg border border-white/10 bg-slate-950/60 p-3">
                <Sun className="size-4 text-solar" aria-hidden />
                <p className="mt-2 font-mono text-lg font-semibold text-white">{payload.energy_kwh}</p>
                <p className="font-mono text-[10px] uppercase text-slate-500">kWh injected</p>
              </div>
              <div className="rounded-lg border border-white/10 bg-slate-950/60 p-3">
                <Zap className="size-4 text-ledger" aria-hidden />
                <p className="mt-2 font-mono text-lg font-semibold text-white">${payload.revenue}</p>
                <p className="font-mono text-[10px] uppercase text-slate-500">STEG revenue</p>
              </div>
            </div>
          </div>

          <div className="bg-slate-900/90 p-5 md:p-6">
            <div className="flex items-baseline justify-between">
              <p className={labelClass}>Revenue split · latest event</p>
              {breakdown && <p className="font-mono text-[10px] text-slate-500">{formatTimestamp(breakdown.timestamp)}</p>}
            </div>
            {breakdown ? (
              <>
                <div className="mt-1 grid grid-cols-2 gap-3">
                  <div className="rounded-lg border border-azure/30 bg-azure/5 p-3">
                    <p className="font-mono text-[11px] text-azure">Owner {ownerPct.toFixed(0)}%</p>
                    <p className="mt-1 font-mono text-xl font-semibold text-white">{formatUSD(ownerTotal)}</p>
                  </div>
                  <div className="rounded-lg border border-solar/30 bg-solar/5 p-3">
                    <p className="font-mono text-[11px] text-solar">Investors {(100 - ownerPct).toFixed(0)}%</p>
                    <p className="mt-1 font-mono text-xl font-semibold text-white">{formatUSD(investorTotal)}</p>
                  </div>
                </div>
                <ul className="mt-4 flex flex-col gap-3">
                  {breakdown.distribution.map((share) => (
                    <li key={`${share.holderId}-${share.isTreasury}`}>
                      <div className="flex items-center justify-between text-sm">
                        <span className="text-slate-300">
                          {share.label}
                          <span className="ml-2 font-mono text-xs text-slate-500">
                            {share.tokens} tok · {share.percent.toFixed(0)}%
                          </span>
                        </span>
                        <span className="font-mono font-semibold text-ledger">${share.amount}</span>
                      </div>
                      <div className="mt-1.5 h-1.5 overflow-hidden rounded-full bg-slate-800">
                        <div
                          className={cn('h-full rounded-full', share.holderId === selected.ownerId ? 'bg-azure' : 'bg-solar')}
                          style={{ width: `${share.percent}%` }}
                        />
                      </div>
                    </li>
                  ))}
                </ul>
              </>
            ) : (
              <p className="mt-6 text-sm text-slate-500">No production events yet. Run a simulation to see the split.</p>
            )}
          </div>
        </div>

        <div className="border-t border-white/10">
          <div className="flex items-center justify-between px-5 py-4 md:px-6">
            <h4 className="font-semibold text-white">Injection history</h4>
            <span className="font-mono text-xs text-slate-500">{projectHistory.length} events</span>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full min-w-[44rem] text-sm">
              <thead>
                <tr className="text-left font-mono text-[11px] uppercase tracking-wider text-slate-500">
                  <th className="px-5 py-3 font-medium md:px-6">Timestamp</th>
                  <th className="px-3 py-3 text-right font-medium">energy_kwh</th>
                  <th className="px-3 py-3 text-right font-medium">revenue</th>
                  <th className="px-3 py-3 text-right font-medium">Holders</th>
                  <th className="px-5 py-3 font-medium md:px-6">contract_transaction_id</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/5">
                {projectHistory.length === 0 && (
                  <tr>
                    <td colSpan={5} className="px-6 py-8 text-center text-slate-500">
                      No events for this project yet.
                    </td>
                  </tr>
                )}
                {projectHistory.map((event, i) => (
                  <tr key={event.id} className={cn('transition', i === 0 && 'bg-ledger/[0.04]')}>
                    <td className="px-5 py-3 font-mono text-xs text-slate-300 md:px-6">{formatTimestamp(event.timestamp)}</td>
                    <td className="px-3 py-3 text-right font-mono text-slate-200">{event.energy_kwh}</td>
                    <td className="px-3 py-3 text-right font-mono text-ledger">${event.revenue}</td>
                    <td className="px-3 py-3 text-right font-mono text-slate-400">{event.distribution.length}</td>
                    <td className="px-5 py-3 font-mono text-xs text-azure md:px-6">{event.contract_transaction_id}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </Panel>
    </section>
  )
}
