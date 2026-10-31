'use client'

import { Check, Hexagon, Rocket, RotateCcw, XCircle } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { REGIONS } from '@/lib/enerx/forecast'
import type { DeployState, NewProjectInput, Region } from '@/lib/enerx/types'
import { DEPLOY_STEPS, INVESTOR_ALLOCATION, OWNER_RETAINED, TOTAL_SUPPLY, formatUSD } from '@/lib/enerx/utils'
import { cn } from '@/lib/utils'
import { Panel, inputClass, labelClass } from '../primitives'

interface ProjectFormProps {
  deployState: DeployState
  onDeploy: (input: NewProjectInput) => Promise<boolean>
  onReset: () => void
}

const EMPTY_FORM = {
  name: '',
  description: '',
  targetFunding: '42000',
  tokenName: '',
  tokenSymbol: '',
  region: 'Djerba' as Region,
  capacityKwp: '24',
}

export function ProjectForm({ deployState, onDeploy, onReset }: ProjectFormProps) {
  const [form, setForm] = useState(EMPTY_FORM)
  const deploying = deployState.status === 'deploying'
  const target = Number(form.targetFunding) || 0

  const update = (key: keyof typeof EMPTY_FORM) => (e: { target: { value: string } }) =>
    setForm((prev) => ({ ...prev, [key]: key === 'tokenSymbol' ? e.target.value.toUpperCase().replace(/[^A-Z]/g, '') : e.target.value }))

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    const ok = await onDeploy({
      name: form.name.trim(),
      description: form.description.trim(),
      targetFunding: target,
      tokenName: form.tokenName.trim(),
      tokenSymbol: form.tokenSymbol,
      region: form.region,
      capacityKwp: Number(form.capacityKwp) || 1,
    })
    if (ok) setForm(EMPTY_FORM)
  }

  return (
    <div className="grid gap-5 lg:grid-cols-[1fr_24rem]">
      <Panel className="p-5 md:p-6">
        <h3 className="flex items-center gap-2 text-lg font-semibold text-white">
          <Rocket className="size-5 text-solar" aria-hidden /> Create project
        </h3>
        <form onSubmit={handleSubmit} className="mt-5 grid gap-4 sm:grid-cols-2">
          <div className="sm:col-span-2">
            <label htmlFor="pf-name" className={labelClass}>
              Project name
            </label>
            <input id="pf-name" required value={form.name} onChange={update('name')} placeholder="Hammamet Coastal Rooftops" className={inputClass} disabled={deploying} />
          </div>
          <div className="sm:col-span-2">
            <label htmlFor="pf-desc" className={labelClass}>
              Description
            </label>
            <textarea
              id="pf-desc"
              required
              rows={3}
              value={form.description}
              onChange={update('description')}
              placeholder="Rooftop PV across 14 homes injecting into the STEG grid during evening peak."
              className={cn(inputClass, 'resize-none')}
              disabled={deploying}
            />
          </div>
          <div>
            <label htmlFor="pf-target" className={labelClass}>
              Target funding ($)
            </label>
            <input id="pf-target" type="number" min={700} step={100} required value={form.targetFunding} onChange={update('targetFunding')} className={`${inputClass} font-mono`} disabled={deploying} />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label htmlFor="pf-region" className={labelClass}>
                Region
              </label>
              <select id="pf-region" value={form.region} onChange={update('region')} className={inputClass} disabled={deploying}>
                {REGIONS.map((r) => (
                  <option key={r}>{r}</option>
                ))}
              </select>
            </div>
            <div>
              <label htmlFor="pf-kwp" className={labelClass}>
                kWp
              </label>
              <input id="pf-kwp" type="number" min={1} required value={form.capacityKwp} onChange={update('capacityKwp')} className={`${inputClass} font-mono`} disabled={deploying} />
            </div>
          </div>
          <div>
            <label htmlFor="pf-token-name" className={labelClass}>
              Token name
            </label>
            <input id="pf-token-name" required value={form.tokenName} onChange={update('tokenName')} placeholder="Hammamet Solar" className={inputClass} disabled={deploying} />
          </div>
          <div>
            <label htmlFor="pf-symbol" className={labelClass}>
              Token symbol
            </label>
            <input
              id="pf-symbol"
              required
              minLength={2}
              maxLength={6}
              value={form.tokenSymbol}
              onChange={update('tokenSymbol')}
              placeholder="HMT"
              className={`${inputClass} font-mono uppercase`}
              disabled={deploying}
            />
          </div>

          <div className="grid grid-cols-3 gap-px overflow-hidden rounded-lg border border-white/10 bg-white/5 sm:col-span-2">
            {[
              { k: 'Total supply', v: `${TOTAL_SUPPLY} · 0 dec` },
              { k: 'Owner retains', v: `${OWNER_RETAINED} tokens` },
              { k: 'Price / token', v: formatUSD(target / INVESTOR_ALLOCATION) },
            ].map((item) => (
              <div key={item.k} className="bg-slate-950/80 px-3 py-2.5">
                <p className="font-mono text-[10px] uppercase tracking-wider text-slate-500">{item.k}</p>
                <p className="mt-0.5 font-mono text-sm text-slate-100">{item.v}</p>
              </div>
            ))}
          </div>

          <button
            type="submit"
            disabled={deploying}
            className="inline-flex items-center justify-center gap-2 rounded-lg bg-solar px-5 py-3 text-sm font-semibold text-slate-950 shadow-[0_0_30px_-8px_rgba(255,102,34,0.8)] transition hover:brightness-110 disabled:opacity-60 sm:col-span-2"
          >
            <Hexagon className="size-4" aria-hidden /> {deploying ? 'Deploying to Hedera…' : 'Deploy HTS token'}
          </button>
        </form>
      </Panel>

      <DeployStatus state={deployState} onReset={onReset} />
    </div>
  )
}

function DeployStatus({ state, onReset }: { state: DeployState; onReset: () => void }) {
  return (
    <Panel className="relative flex flex-col overflow-hidden p-5 md:p-6">
      <h3 className="font-mono text-xs uppercase tracking-[0.2em] text-slate-400">HTS deployment</h3>

      {state.status === 'idle' && (
        <div className="flex flex-1 flex-col items-center justify-center gap-3 py-10 text-center">
          <Hexagon className="size-12 text-slate-700" aria-hidden />
          <p className="text-sm text-slate-500">Submit the form to mint a new 100-unit HTS token.</p>
        </div>
      )}

      {state.status === 'deploying' && (
        <div className="flex flex-1 flex-col gap-6 py-4" role="status" aria-live="polite">
          <div className="relative mx-auto flex size-32 items-center justify-center">
            <span className="absolute inset-0 animate-spin rounded-full border-2 border-dashed border-azure/40 [animation-duration:6s]" />
            <span className="absolute inset-3 animate-spin rounded-full border-2 border-transparent border-t-solar border-r-solar [animation-duration:1.2s]" />
            <span className="absolute inset-7 animate-pulse rounded-full bg-solar/20 blur-md" />
            <Hexagon className="relative size-10 text-solar" aria-hidden />
          </div>
          <ol className="flex flex-col gap-2.5">
            {DEPLOY_STEPS.map((step, i) => {
              const done = i < state.step
              const current = i === state.step
              return (
                <li key={step} className={cn('flex items-center gap-2.5 font-mono text-xs', done ? 'text-ledger' : current ? 'text-white' : 'text-slate-600')}>
                  <span
                    className={cn(
                      'flex size-4 shrink-0 items-center justify-center rounded-full border',
                      done ? 'border-ledger bg-ledger/20' : current ? 'animate-pulse border-solar' : 'border-slate-700',
                    )}
                  >
                    {done && <Check className="size-2.5" aria-hidden />}
                  </span>
                  {step}
                </li>
              )
            })}
          </ol>
        </div>
      )}

      {state.status === 'success' && (
        <div className="flex flex-1 flex-col gap-4 py-4">
          <div className="flex items-center gap-3">
            <span className="flex size-10 items-center justify-center rounded-full bg-ledger/15 ring-1 ring-ledger/50 shadow-[0_0_30px_rgba(52,211,153,0.5)]">
              <Check className="size-5 text-ledger" aria-hidden />
            </span>
            <div>
              <p className="font-semibold text-white">Token live on testnet</p>
              <p className="text-xs text-slate-400">
                {state.projectName} · ${state.symbol}
              </p>
            </div>
          </div>
          <div className="rounded-xl border border-ledger/40 bg-slate-950 p-4">
            <p className="font-mono text-[10px] uppercase tracking-wider text-slate-500">hedera_token_id</p>
            <p className="mt-1 font-mono text-2xl font-semibold text-ledger">{state.tokenId}</p>
          </div>
          <p className="text-xs leading-relaxed text-slate-400">
            30 tokens associated to your treasury. 70 tokens are now listed on the primary market.
          </p>
          <button type="button" onClick={onReset} className="mt-auto inline-flex items-center justify-center gap-2 rounded-lg border border-white/15 px-4 py-2 text-sm text-slate-200 hover:border-white/30">
            <RotateCcw className="size-4" aria-hidden /> Deploy another
          </button>
        </div>
      )}

      {state.status === 'error' && (
        <div className="flex flex-1 flex-col items-center justify-center gap-3 py-10 text-center" role="alert">
          <XCircle className="size-10 text-rose-400" aria-hidden />
          <p className="text-sm text-rose-300">{state.message}</p>
          <button type="button" onClick={onReset} className="rounded-lg border border-white/15 px-4 py-2 text-sm text-slate-200">
            Dismiss
          </button>
        </div>
      )}
    </Panel>
  )
}
