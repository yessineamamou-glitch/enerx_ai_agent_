import { ShieldAlert, ShieldCheck, Wallet } from 'lucide-react'
import type { Holdings, KycRecord, Listing, Profile, Project } from '@/lib/enerx/types'
import { formatUSD, tokenPrice } from '@/lib/enerx/utils'
import { Panel, SectionHeader } from '../primitives'
import { CampaignCard } from './campaign-card'
import { SecondaryMarket } from './secondary-market'

interface InvestTabProps {
  projects: Project[]
  profiles: Profile[]
  activeProfile: Profile
  kyc: KycRecord
  holdings: Holdings
  listings: Listing[]
  pendingBuyProjectId: string | null
  pendingListingId: string | null
  isCreatingListing: boolean
  onOpenKyc: () => void
  onBuyPrimary: (projectId: string, quantity: number) => void
  onCreateListing: (projectId: string, amount: number, unitPrice: number) => void
  onBuyListing: (listingId: string) => void
  onCancelListing: (listingId: string) => void
}

function DidBadge({ kyc, onOpenKyc }: { kyc: KycRecord; onOpenKyc: () => void }) {
  if (kyc.verified) {
    return (
      <div className="flex items-center gap-3 rounded-xl border border-ledger/40 bg-ledger/10 px-4 py-3 shadow-[0_0_30px_-10px_rgba(52,211,153,0.6)]">
        <ShieldCheck className="size-5 shrink-0 text-ledger" aria-hidden />
        <div className="min-w-0">
          <p className="text-sm font-semibold text-ledger">DID Status: Verified</p>
          <p className="max-w-72 truncate font-mono text-[11px] text-slate-400" title={kyc.did ?? undefined}>
            {kyc.did}
          </p>
        </div>
      </div>
    )
  }
  return (
    <button
      type="button"
      onClick={onOpenKyc}
      className="flex items-center gap-3 rounded-xl border border-amber-400/50 bg-amber-400/10 px-4 py-3 text-left shadow-[0_0_30px_-10px_rgba(251,191,36,0.7)] transition hover:bg-amber-400/15"
    >
      <ShieldAlert className="size-5 shrink-0 animate-pulse text-amber-400" aria-hidden />
      <span>
        <span className="block text-sm font-semibold text-amber-300">DID Status: Not Verified</span>
        <span className="block font-mono text-[11px] text-amber-200/70">Click to complete KYC · required to invest</span>
      </span>
    </button>
  )
}

export function InvestTab(props: InvestTabProps) {
  const { projects, activeProfile, kyc, holdings, onOpenKyc } = props

  const myPositions = projects
    .map((p) => ({ project: p, tokens: holdings[p.id]?.[activeProfile.id] ?? 0 }))
    .filter((pos) => pos.tokens > 0)
  const portfolioValue = myPositions.reduce((sum, pos) => sum + pos.tokens * tokenPrice(pos.project), 0)
  const totalTokens = myPositions.reduce((sum, pos) => sum + pos.tokens, 0)

  return (
    <div className="enerx-grid-bg">
      <div className="mx-auto flex max-w-7xl flex-col gap-10 px-4 py-10 md:px-6 md:py-14">
        <SectionHeader
          eyebrow="Primary & secondary markets"
          title="Invest in tokenized solar"
          description="Each installation mints exactly 100 HTS tokens (0 decimals · 1 token = 1% ownership). Participants can buy and sell verified P2P allocations."
          action={<DidBadge kyc={kyc} onOpenKyc={onOpenKyc} />}
        />

        <Panel className="grid gap-px overflow-hidden bg-white/5 sm:grid-cols-3">
          {[
            { label: 'Virtual balance', value: formatUSD(activeProfile.balance) },
            { label: 'Tokens held', value: `${totalTokens} across ${myPositions.length} projects` },
            { label: 'Portfolio value (at issue)', value: formatUSD(portfolioValue, 0) },
          ].map((item) => (
            <div key={item.label} className="flex items-center gap-3 bg-slate-900/90 px-5 py-4">
              <Wallet className="size-4 text-slate-500" aria-hidden />
              <div>
                <p className="font-mono text-[11px] uppercase tracking-wider text-slate-500">{item.label}</p>
                <p className="mt-0.5 font-semibold text-white">{item.value}</p>
              </div>
            </div>
          ))}
        </Panel>

        <section aria-labelledby="primary-heading" className="flex flex-col gap-5">
          <div className="flex items-baseline justify-between">
            <h3 id="primary-heading" className="text-xl font-semibold text-white">
              Primary market
            </h3>
            <p className="font-mono text-xs text-slate-500">HTS · TokenCreate → CryptoTransfer</p>
          </div>
          <div className="grid gap-5 lg:grid-cols-2">
            {projects.map((project) => (
              <CampaignCard
                key={project.id}
                project={project}
                activeProfile={activeProfile}
                verified={kyc.verified}
                isPending={props.pendingBuyProjectId === project.id}
                isBusy={props.pendingBuyProjectId !== null}
                onBuy={props.onBuyPrimary}
                onOpenKyc={onOpenKyc}
              />
            ))}
          </div>
        </section>

        <SecondaryMarket
          projects={projects}
          profiles={props.profiles}
          activeProfile={activeProfile}
          verified={kyc.verified}
          holdings={holdings}
          listings={props.listings}
          pendingListingId={props.pendingListingId}
          isCreatingListing={props.isCreatingListing}
          onCreateListing={props.onCreateListing}
          onBuyListing={props.onBuyListing}
          onCancelListing={props.onCancelListing}
          onOpenKyc={onOpenKyc}
        />
      </div>
    </div>
  )
}
