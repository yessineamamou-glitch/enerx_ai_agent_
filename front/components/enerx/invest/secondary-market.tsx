'use client'

import { ArrowLeftRight, Tag } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import type { Holdings, Listing, Profile, Project } from '@/lib/enerx/types'
import { formatUSD, tokenPrice } from '@/lib/enerx/utils'
import { Panel, Spinner, inputClass, labelClass } from '../primitives'

interface SecondaryMarketProps {
  projects: Project[]
  profiles: Profile[]
  activeProfile: Profile
  verified: boolean
  holdings: Holdings
  listings: Listing[]
  pendingListingId: string | null
  isCreatingListing: boolean
  onCreateListing: (projectId: string, amount: number, unitPrice: number) => void
  onBuyListing: (listingId: string) => void
  onCancelListing: (listingId: string) => void
  onOpenKyc: () => void
}

export function SecondaryMarket({
  projects,
  profiles,
  activeProfile,
  verified,
  holdings,
  listings,
  pendingListingId,
  isCreatingListing,
  onCreateListing,
  onBuyListing,
  onCancelListing,
  onOpenKyc,
}: SecondaryMarketProps) {
  const positions = projects
    .map((project) => {
      const held = holdings[project.id]?.[activeProfile.id] ?? 0
      const listed = listings
        .filter((l) => l.projectId === project.id && l.sellerId === activeProfile.id)
        .reduce((sum, l) => sum + l.amount, 0)
      return { project, held, free: held - listed }
    })
    .filter((p) => p.held > 0)

  const [selectedProjectId, setSelectedProjectId] = useState('')
  const [amount, setAmount] = useState('1')
  const [unitPrice, setUnitPrice] = useState('')

  const selected = positions.find((p) => p.project.id === selectedProjectId) ?? positions[0]

  function handleSubmit(e: FormEvent) {
    e.preventDefault()
    if (!selected) return
    onCreateListing(selected.project.id, Number(amount), Number(unitPrice || tokenPrice(selected.project)))
  }

  return (
    <section aria-labelledby="secondary-heading" className="flex flex-col gap-5">
      <div className="flex items-baseline justify-between">
        <h3 id="secondary-heading" className="flex items-center gap-2 text-xl font-semibold text-white">
          <ArrowLeftRight className="size-5 text-azure" aria-hidden /> Secondary market
        </h3>
        <p className="font-mono text-xs text-slate-500">Peer-to-peer · atomic HTS swap</p>
      </div>

      <div className="grid gap-5 lg:grid-cols-[22rem_1fr]">
        <Panel className="p-5">
          <h4 className="flex items-center gap-2 font-semibold text-white">
            <Tag className="size-4 text-solar" aria-hidden /> Create sale listing
          </h4>
          {positions.length === 0 ? (
            <p className="mt-4 rounded-lg border border-dashed border-white/10 p-4 text-sm leading-relaxed text-slate-400">
              {activeProfile.name} holds no tokens yet. Buy into a primary campaign or switch profile to list tokens.
            </p>
          ) : (
            <form onSubmit={handleSubmit} className="mt-4 flex flex-col gap-4">
              <div>
                <label htmlFor="listing-project" className={labelClass}>
                  Token
                </label>
                <select
                  id="listing-project"
                  value={selected?.project.id}
                  onChange={(e) => setSelectedProjectId(e.target.value)}
                  className={inputClass}
                >
                  {positions.map(({ project, free, held }) => (
                    <option key={project.id} value={project.id}>
                      {project.tokenSymbol} · {free} free / {held} held
                    </option>
                  ))}
                </select>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label htmlFor="listing-amount" className={labelClass}>
                    Amount
                  </label>
                  <input
                    id="listing-amount"
                    type="number"
                    min={1}
                    max={selected?.free}
                    step={1}
                    required
                    value={amount}
                    onChange={(e) => setAmount(e.target.value)}
                    className={`${inputClass} font-mono`}
                  />
                </div>
                <div>
                  <label htmlFor="listing-price" className={labelClass}>
                    Unit price ($)
                  </label>
                  <input
                    id="listing-price"
                    type="number"
                    min={0.01}
                    step={0.01}
                    placeholder={selected ? tokenPrice(selected.project).toFixed(2) : ''}
                    value={unitPrice}
                    onChange={(e) => setUnitPrice(e.target.value)}
                    className={`${inputClass} font-mono`}
                  />
                </div>
              </div>
              <p className="font-mono text-[11px] text-slate-500">
                Total ask:{' '}
                <span className="text-slate-200">
                  {formatUSD(Number(amount || 0) * Number(unitPrice || (selected ? tokenPrice(selected.project) : 0)))}
                </span>
              </p>
              {verified ? (
                <button
                  type="submit"
                  disabled={isCreatingListing}
                  className="inline-flex items-center justify-center gap-2 rounded-lg bg-solar px-4 py-2.5 text-sm font-semibold text-slate-950 transition hover:brightness-110 disabled:opacity-60"
                >
                  {isCreatingListing ? (
                    <>
                      <Spinner /> Publishing…
                    </>
                  ) : (
                    'Publish listing'
                  )}
                </button>
              ) : (
                <button
                  type="button"
                  onClick={onOpenKyc}
                  className="rounded-lg border border-amber-400/50 px-4 py-2.5 text-sm font-semibold text-amber-300 hover:bg-amber-400/10"
                >
                  Verify DID to trade
                </button>
              )}
            </form>
          )}
        </Panel>

        <Panel className="overflow-hidden">
          <div className="flex items-center justify-between border-b border-white/10 px-5 py-4">
            <h4 className="font-semibold text-white">Order book</h4>
            <span className="font-mono text-xs text-slate-500">{listings.length} open listings</span>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full min-w-[36rem] text-sm">
              <thead>
                <tr className="text-left font-mono text-[11px] uppercase tracking-wider text-slate-500">
                  <th className="px-5 py-3 font-medium">Token</th>
                  <th className="px-3 py-3 font-medium">Seller</th>
                  <th className="px-3 py-3 text-right font-medium">Amount</th>
                  <th className="px-3 py-3 text-right font-medium">Unit price</th>
                  <th className="px-3 py-3 text-right font-medium">Total</th>
                  <th className="px-5 py-3 text-right font-medium">
                    <span className="sr-only">Action</span>
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/5">
                {listings.length === 0 && (
                  <tr>
                    <td colSpan={6} className="px-5 py-10 text-center text-slate-500">
                      No open listings. Publish one to start the market.
                    </td>
                  </tr>
                )}
                {listings.map((listing) => {
                  const project = projects.find((p) => p.id === listing.projectId)
                  const seller = profiles.find((p) => p.id === listing.sellerId)
                  const own = listing.sellerId === activeProfile.id
                  const total = listing.amount * listing.unitPrice
                  const premium = project ? (listing.unitPrice / tokenPrice(project) - 1) * 100 : 0
                  const pending = pendingListingId === listing.id
                  return (
                    <tr key={listing.id} className="transition hover:bg-white/[0.02]">
                      <td className="px-5 py-3">
                        <span className="font-mono font-semibold text-azure">${project?.tokenSymbol}</span>
                        <span className="block text-xs text-slate-500">{project?.name}</span>
                      </td>
                      <td className="px-3 py-3 text-slate-300">
                        {seller?.name}
                        {own && <span className="ml-1.5 font-mono text-[10px] text-solar">(you)</span>}
                      </td>
                      <td className="px-3 py-3 text-right font-mono text-slate-200">{listing.amount}</td>
                      <td className="px-3 py-3 text-right font-mono text-slate-200">
                        {formatUSD(listing.unitPrice)}
                        <span className={`block text-[10px] ${premium >= 0 ? 'text-ledger' : 'text-rose-400'}`}>
                          {premium >= 0 ? '+' : ''}
                          {premium.toFixed(1)}% vs issue
                        </span>
                      </td>
                      <td className="px-3 py-3 text-right font-mono font-semibold text-white">{formatUSD(total)}</td>
                      <td className="px-5 py-3 text-right">
                        {own ? (
                          <button
                            type="button"
                            onClick={() => onCancelListing(listing.id)}
                            className="rounded-md border border-white/15 px-3 py-1.5 text-xs font-medium text-slate-300 hover:border-rose-400/60 hover:text-rose-300"
                          >
                            Cancel
                          </button>
                        ) : (
                          <button
                            type="button"
                            onClick={() => (verified ? onBuyListing(listing.id) : onOpenKyc())}
                            disabled={pendingListingId !== null}
                            className="inline-flex min-w-20 items-center justify-center gap-1.5 rounded-md bg-azure/15 px-3 py-1.5 text-xs font-semibold text-azure ring-1 ring-azure/40 transition hover:bg-azure/25 disabled:opacity-50"
                          >
                            {pending ? <Spinner className="size-3" /> : verified ? 'Buy now' : 'Verify'}
                          </button>
                        )}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </Panel>
      </div>
    </section>
  )
}
