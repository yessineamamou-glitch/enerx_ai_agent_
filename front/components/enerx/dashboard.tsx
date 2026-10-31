'use client'

import { useCallback, useEffect, useState } from 'react'
import { apiDelete, apiRequest, sleep } from '@/lib/enerx/api'
import {
  INITIAL_HISTORY,
  INITIAL_HOLDINGS,
  INITIAL_KYC,
  INITIAL_LISTINGS,
  INITIAL_PROFILES,
  INITIAL_PROJECTS,
} from '@/lib/enerx/mock-data'
import type {
  DeployState,
  ForecastRange,
  Holdings,
  KycRecord,
  KycSubmission,
  Listing,
  NewProjectInput,
  ProductionEvent,
  Profile,
  Project,
  Region,
  TabId,
  Toast,
} from '@/lib/enerx/types'
import {
  DEPLOY_STEPS,
  INVESTOR_ALLOCATION,
  OWNER_RETAINED,
  TOTAL_SUPPLY,
  formatUSD,
  makeContractTxId,
  makeDid,
  makeHtsTxId,
  makeId,
  makeTokenId,
  splitRevenue,
  tokenPrice,
} from '@/lib/enerx/utils'
import { AiPredictorTab } from './ai/ai-predictor-tab'
import { HomeTab } from './home-tab'
import { InvestTab } from './invest/invest-tab'
import { KycModal } from './invest/kyc-modal'
import { OwnerTab } from './owner/owner-tab'
import { ToastStack } from './toast-stack'
import { TopNav } from './top-nav'

const SIMULATED_PRODUCTION = { energy_kwh: '520.00', revenue: '104.00' } as const

type BackendProject = {
  id: number
  owner_id: number
  name: string
  description: string | null
  token_name: string
  token_symbol: string
  token_id: number
  token_supply: number
  target_amount: number
  status: string
  hedera_token_id?: string
}

type BackendInvestment = {
  transaction_id: string
  project_status?: string
  status?: string
}

type BackendReceipt = {
  status?: string
  transaction_id: string
}

type BackendVerification = {
  user_id: number
  did: string | null
  identity_verified: boolean
  investor_verified: boolean
  owner_verified: boolean
}

type BackendListing = {
  id: number
  user_id: number
  token_id: number
  project_id?: number
  u_price: string | number
  amount: number
}

type BackendProjectCreate = BackendProject & {
  commitment_file_id: string
  commitment_transaction_id: string
}

type BackendProduction = {
  contract_transaction_id: string
  distributions?: Array<{ user_id: number; token_amount: number; amount: string | number }>
}

const backendUserId = (profile: Profile) => {
  if (profile.backendId) return profile.backendId
  const match = profile.id.match(/\d+$/)
  if (!match) throw new Error(`No backend user ID is configured for ${profile.id}`)
  return Number(match[0])
}

const backendProjectId = (project: Project) => {
  if (project.backendId) return project.backendId
  const match = project.id.match(/\d+$/)
  if (!match) throw new Error(`No backend project ID is configured for ${project.id}`)
  return Number(match[0])
}

const backendTokenId = (project: Project) => {
  if (!project.backendTokenId) throw new Error(`No backend token ID is configured for ${project.name}`)
  return project.backendTokenId
}

function mapBackendProject(project: BackendProject, profiles: Profile[], previous?: Project): Project {
  const soldTokens = Math.max(0, project.token_supply - OWNER_RETAINED)
  return {
    id: previous?.id ?? `p-${project.id}`,
    backendId: project.id,
    backendTokenId: project.token_id,
    name: project.name,
    location: previous?.location ?? 'Tunisia',
    region: previous?.region ?? 'Tunis',
    description: project.description ?? '',
    targetFunding: Number(project.target_amount),
    tokenName: project.token_name,
    tokenSymbol: project.token_symbol,
    hederaTokenId: project.hedera_token_id ?? previous?.hederaTokenId ?? '',
    ownerId: previous?.ownerId ?? profiles.find((profile) => profile.backendId === project.owner_id)?.id ?? `user-${project.owner_id}`,
    totalSupply: TOTAL_SUPPLY,
    ownerRetained: OWNER_RETAINED,
    availableTokens: Math.max(0, INVESTOR_ALLOCATION - soldTokens),
    // The current backend ProjectResponse does not expose the installation
    // capacity, so keep the existing value or use a safe demo default.
    capacityKwp: previous?.capacityKwp && previous.capacityKwp > 0 ? previous.capacityKwp : 10,
  }
}

export function EnerxDashboard() {
  // Navigation
  const [activeTab, setActiveTab] = useState<TabId>('home')

  // Profiles & identity — GET /profiles, POST /kyc/verify
  const [profiles, setProfiles] = useState<Profile[]>(INITIAL_PROFILES)
  const [activeProfileId, setActiveProfileId] = useState<string>('investor-1')
  const [kycRecords, setKycRecords] = useState<Record<string, KycRecord>>(INITIAL_KYC)
  const [isKycModalOpen, setIsKycModalOpen] = useState(false)
  const [kycStatus, setKycStatus] = useState<'idle' | 'loading' | 'pending' | 'error'>('idle')

  // Primary & secondary markets — GET /projects, POST /invest/buy, /market/listings
  const [projects, setProjects] = useState<Project[]>(INITIAL_PROJECTS)
  const [holdings, setHoldings] = useState<Holdings>(INITIAL_HOLDINGS)
  const [listings, setListings] = useState<Listing[]>(INITIAL_LISTINGS)
  const [pendingBuyProjectId, setPendingBuyProjectId] = useState<string | null>(null)
  const [pendingListingId, setPendingListingId] = useState<string | null>(null)
  const [isCreatingListing, setIsCreatingListing] = useState(false)

  // Owner — POST /projects, POST /production/simulate
  const [deployState, setDeployState] = useState<DeployState>({ status: 'idle' })
  const [productionHistory, setProductionHistory] = useState<ProductionEvent[]>(INITIAL_HISTORY)
  const [isSimulating, setIsSimulating] = useState(false)
  const [lastProductionEvent, setLastProductionEvent] = useState<ProductionEvent | null>(INITIAL_HISTORY[0])

  // AI predictor — GET /ai/forecast
  const [aiProjectId, setAiProjectId] = useState<string>(INITIAL_PROJECTS[0].id)
  const [aiRegion, setAiRegion] = useState<Region>(INITIAL_PROJECTS[0].region)
  const [forecastRange, setForecastRange] = useState<ForecastRange>('7d')

  // Notifications
  const [toasts, setToasts] = useState<Toast[]>([])

  const activeProfile = profiles.find((p) => p.id === activeProfileId) ?? profiles[0]
  const activeKyc = kycRecords[activeProfile.id] ?? {
    verified: false,
    did: null,
    identityVerified: false,
    investorVerified: false,
    ownerVerified: false,
  }
  const participantVerified = activeKyc.identityVerified && (activeKyc.investorVerified || activeKyc.ownerVerified)

  const updateKycRecord = (profile: Profile, status: BackendVerification, details?: Pick<KycRecord, 'legalName' | 'email'>) => {
    const verified = status.identity_verified && (status.investor_verified || status.owner_verified)
    setKycRecords((previous) => ({
      ...previous,
      [profile.id]: {
        verified,
        did: status.did,
        identityVerified: status.identity_verified,
        investorVerified: status.investor_verified,
        ownerVerified: status.owner_verified,
        ...details,
      },
    }))
    return verified
  }

  useEffect(() => {
    let cancelled = false
    Promise.all(
      profiles.map(async (profile) => {
        try {
          const status = await apiRequest<BackendVerification>(`/auth/verification/${backendUserId(profile)}`)
          return { profile, status }
        } catch {
          return null
        }
      }),
    ).then((results) => {
      if (cancelled) return
      for (const result of results) {
        if (result) updateKycRecord(result.profile, result.status)
      }
    })
    apiRequest<BackendProject[]>('/project/')
      .then((items) => {
        if (cancelled || !items.length) return
        setProjects((previous) => {
          const mappedProjects = items.map((item) => {
            const previousProject = previous.find((project) => project.backendId === item.id)
            return mapBackendProject(item, profiles, previousProject)
          })
          setAiProjectId(mappedProjects[0].id)
          setAiRegion(mappedProjects[0].region)
          return mappedProjects
        })
      })
      .catch(() => {
        // Keep the existing demo data when the API is not running yet.
      })
    return () => {
      cancelled = true
    }
  }, [])

  useEffect(() => {
    if (!projects.length) return
    let cancelled = false
    apiRequest<BackendListing[]>('/marketplace/listings')
      .then((items) => {
        if (cancelled) return
        setListings(
          items
            .map((item) => {
              const project = projects.find((candidate) => candidate.backendId === item.project_id)
              const seller = profiles.find((profile) => profile.backendId === item.user_id)
              if (!project || !seller) return null
              return {
                id: String(item.id),
                projectId: project.id,
                sellerId: seller.id,
                amount: Number(item.amount),
                unitPrice: Number(item.u_price),
              }
            })
            .filter((item): item is Listing => item !== null),
        )
      })
      .catch(() => {
        // Keep demo listings when the marketplace API is unavailable.
      })
    return () => {
      cancelled = true
    }
  }, [projects, profiles])

  const dismissToast = useCallback((id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id))
  }, [])

  const pushToast = useCallback(
    (toast: Omit<Toast, 'id'>, durationMs = 6000) => {
      const id = makeId('toast')
      setToasts((prev) => [...prev.slice(-3), { ...toast, id }])
      setTimeout(() => dismissToast(id), durationMs)
    },
    [dismissToast],
  )

  const fail = (title: string, description?: string) => pushToast({ variant: 'error', title, description })

  const adjustBalances = (deltas: Record<string, number>) => {
    setProfiles((prev) =>
      prev.map((p) => (deltas[p.id] ? { ...p, balance: Math.round((p.balance + deltas[p.id]) * 100) / 100 } : p)),
    )
  }

  const transferTokens = (projectId: string, fromId: string | null, toId: string, amount: number) => {
    setHoldings((prev) => {
      const projectHoldings = { ...(prev[projectId] ?? {}) }
      if (fromId) projectHoldings[fromId] = (projectHoldings[fromId] ?? 0) - amount
      projectHoldings[toId] = (projectHoldings[toId] ?? 0) + amount
      return { ...prev, [projectId]: projectHoldings }
    })
  }

  async function handleVerifyKyc(submission: KycSubmission) {
    setKycStatus('loading')
    try {
      const result = await apiRequest<{ did: string }>(
        '/auth/did',
        {
          user_id: backendUserId(activeProfile),
          legal_name: submission.legalName,
          email: submission.email,
          hedera_id: activeProfile.hederaAccount,
        },
        () => ({ did: makeDid(activeProfile.hederaAccount) }),
        1800,
      )
      const verification = await apiRequest<BackendVerification>(
        `/auth/verification/${backendUserId(activeProfile)}`,
      )
      const verified = updateKycRecord(activeProfile, { ...verification, did: verification.did ?? result.did }, {
        legalName: submission.legalName,
        email: submission.email,
      })
      if (!verified) {
        setKycStatus('pending')
        pushToast({
          variant: 'info',
          title: 'DID created; credential verification is pending',
          description: 'A valid participant credential is still required.',
          txId: result.did,
        })
        return
      }
      setKycStatus('idle')
      setIsKycModalOpen(false)
      pushToast({ variant: 'success', title: 'Identity and participant credential verified', txId: result.did })
    } catch {
      setKycStatus('error')
      fail('KYC verification failed', 'The identity service did not respond. Please retry.')
    }
  }

  async function handleBuyPrimary(projectId: string, quantity: number) {
    const project = projects.find((p) => p.id === projectId)
    if (!project) return fail('Campaign not found')
    if (!participantVerified)
      return fail('Participant verification required', 'Complete identity verification and obtain a valid participant credential.')
    if (project.ownerId === activeProfile.id) return fail('Owners cannot buy their own allocation')
    if (!Number.isInteger(quantity) || quantity < 1) return fail('Enter a whole number of tokens (0 decimals)')
    if (project.availableTokens === 0) return fail('Campaign CLOSED', 'All 70 investor tokens have been sold.')
    if (quantity > project.availableTokens)
      return fail('Not enough tokens available', `Only ${project.availableTokens} tokens remain.`)

    const cost = quantity * tokenPrice(project)
    if (activeProfile.balance < cost)
      return fail('Insufficient virtual balance', `Requires ${formatUSD(cost)} · you hold ${formatUSD(activeProfile.balance)}.`)

    setPendingBuyProjectId(projectId)
    try {
      const receipt = await apiRequest<BackendInvestment>(
        '/investment/',
        { project_id: backendProjectId(project), user_id: backendUserId(activeProfile), token_amount: quantity },
        () => ({ status: 'SUCCESS', transaction_id: makeHtsTxId() }),
      )
      const remaining = project.availableTokens - quantity
      setProjects((prev) => prev.map((p) => (p.id === projectId ? { ...p, availableTokens: remaining } : p)))
      transferTokens(projectId, null, activeProfile.id, quantity)
      adjustBalances({ [activeProfile.id]: -cost, [project.ownerId]: cost })
      pushToast({
        variant: 'success',
        title: `Hedera HTS Transaction: ${receipt.status ?? receipt.project_status ?? 'SUCCESS'}`,
        description: `${quantity} ${project.tokenSymbol} transferred for ${formatUSD(cost)}`,
        txId: receipt.transaction_id,
      })
      if (remaining === 0) {
        pushToast({ variant: 'info', title: `${project.name} is now CLOSED`, description: 'Fully funded · 70/70 tokens sold.' })
      }
    } catch {
      fail('HTS transfer failed', 'The transaction was not submitted. No funds were moved.')
    } finally {
      setPendingBuyProjectId(null)
    }
  }

  async function handleCreateListing(projectId: string, amount: number, unitPrice: number) {
    const project = projects.find((item) => item.id === projectId)
    if (!project) return fail('Campaign not found')
    if (!participantVerified)
      return fail('Participant verification required', 'Complete identity verification and obtain a valid participant credential.')
    const held = holdings[projectId]?.[activeProfile.id] ?? 0
    const alreadyListed = listings
      .filter((l) => l.projectId === projectId && l.sellerId === activeProfile.id)
      .reduce((sum, l) => sum + l.amount, 0)
    if (!Number.isInteger(amount) || amount < 1) return fail('Amount must be a whole number of tokens')
    if (!(unitPrice > 0)) return fail('Unit price must be greater than 0')
    if (amount > held - alreadyListed)
      return fail('Insufficient free tokens', `You can list at most ${held - alreadyListed} more tokens.`)

    setIsCreatingListing(true)
    try {
      const listing = await apiRequest<BackendListing>(
        '/marketplace/list',
        {
          user_id: backendUserId(activeProfile),
          token_id: backendTokenId(project),
          amount,
          u_price: unitPrice.toFixed(2),
        },
        () => ({ id: makeId('l'), projectId, sellerId: activeProfile.id, amount, unitPrice }),
        700,
      )
      setListings((prev) => [
        {
          id: String(listing.id),
          projectId,
          sellerId: activeProfile.id,
          amount: Number(listing.amount),
          unitPrice: Number(listing.u_price),
        },
        ...prev,
      ])
      pushToast({ variant: 'info', title: 'Sale listing published', description: `${amount} tokens @ ${formatUSD(unitPrice)}` })
    } catch {
      fail('Could not publish listing')
    } finally {
      setIsCreatingListing(false)
    }
  }

  async function handleBuyListing(listingId: string) {
    const listing = listings.find((l) => l.id === listingId)
    if (!listing) return fail('Listing no longer available')
    if (!participantVerified)
      return fail('Participant verification required', 'Complete identity verification and obtain a valid participant credential.')
    if (listing.sellerId === activeProfile.id) return fail('You cannot buy your own listing')
    const total = listing.amount * listing.unitPrice
    if (activeProfile.balance < total)
      return fail('Insufficient virtual balance', `Requires ${formatUSD(total)} · you hold ${formatUSD(activeProfile.balance)}.`)

    setPendingListingId(listingId)
    try {
      const receipt = await apiRequest<BackendReceipt>(
        '/marketplace/list/buy',
        {
          user_id: backendUserId(activeProfile),
          listing_id: Number(listingId),
          amount: listing.amount,
        },
        () => ({ status: 'SUCCESS', transaction_id: makeHtsTxId() }),
      )
      transferTokens(listing.projectId, listing.sellerId, activeProfile.id, listing.amount)
      adjustBalances({ [activeProfile.id]: -total, [listing.sellerId]: total })
      setListings((prev) => prev.filter((l) => l.id !== listingId))
      const symbol = projects.find((p) => p.id === listing.projectId)?.tokenSymbol ?? ''
      pushToast({
        variant: 'success',
        title: `Hedera HTS Transaction: ${receipt.status ?? 'SUCCESS'}`,
        description: `P2P swap · ${listing.amount} ${symbol} for ${formatUSD(total)}`,
        txId: receipt.transaction_id,
      })
    } catch {
      fail('P2P settlement failed')
    } finally {
      setPendingListingId(null)
    }
  }

  async function handleCancelListing(listingId: string) {
    const listing = listings.find((item) => item.id === listingId)
    if (!listing) return fail('Listing no longer available')
    try {
      await apiDelete(`/marketplace/list/${Number(listingId)}?user_id=${backendUserId(activeProfile)}`)
      setListings((prev) => prev.filter((l) => l.id !== listingId))
      pushToast({ variant: 'info', title: 'Listing cancelled' }, 3000)
    } catch {
      fail('Could not cancel listing')
    }
  }

  async function handleDeployProject(input: NewProjectInput): Promise<boolean> {
    if (!activeKyc.identityVerified || !activeKyc.ownerVerified) {
      fail('Project-owner verification required', 'Complete identity verification and obtain a ProjectOwnerVerification credential.')
      return false
    }
    setDeployState({ status: 'deploying', step: 0 })
    try {
      for (let step = 1; step < DEPLOY_STEPS.length; step++) {
        await sleep(650)
        setDeployState({ status: 'deploying', step })
      }
      const result = await apiRequest<BackendProjectCreate>(
        '/project/',
        {
          user_id: backendUserId(activeProfile),
          name: input.name,
          description: input.description,
          target_amount: input.targetFunding,
          token_name: input.tokenName,
          token_symbol: input.tokenSymbol,
        },
        () => ({ hedera_token_id: makeTokenId() }),
        650,
      )
      const project: Project = {
        id: `p-${result.id}`,
        backendId: result.id,
        backendTokenId: result.token_id,
        name: input.name,
        description: input.description,
        location: `${input.region}, Tunisia`,
        region: input.region,
        targetFunding: input.targetFunding,
        tokenName: input.tokenName,
        tokenSymbol: input.tokenSymbol,
        capacityKwp: input.capacityKwp,
        hederaTokenId: result.hedera_token_id ?? '',
        ownerId: activeProfile.id,
        totalSupply: TOTAL_SUPPLY,
        ownerRetained: OWNER_RETAINED,
        availableTokens: INVESTOR_ALLOCATION,
      }
      setProjects((prev) => [project, ...prev])
      setHoldings((prev) => ({ ...prev, [project.id]: { [activeProfile.id]: OWNER_RETAINED } }))
      setDeployState({
        status: 'success',
        tokenId: result.hedera_token_id ?? '',
        projectName: input.name,
        symbol: input.tokenSymbol,
      })
      pushToast({ variant: 'success', title: 'HTS token deployed', description: input.name, txId: result.hedera_token_id ?? '' })
      return true
    } catch {
      setDeployState({ status: 'error', message: 'Token deployment failed. Please retry.' })
      fail('HTS deployment failed')
      return false
    }
  }

  async function handleSimulateProduction(projectId: string) {
    const project = projects.find((p) => p.id === projectId)
    if (!project) return fail('Select a project to simulate')
    setIsSimulating(true)
    try {
      const response = await apiRequest<BackendProduction>(
        '/prod',
        { project_id: backendProjectId(project), ...SIMULATED_PRODUCTION },
        () => ({ contract_transaction_id: makeContractTxId() }),
        1200,
      )
      const distribution = response.distributions
        ? response.distributions.map((item) => {
            const holder = profiles.find((profile) => profile.backendId === item.user_id)
            return {
              holderId: holder?.id ?? `user-${item.user_id}`,
              label: holder?.name ?? `User ${item.user_id}`,
              tokens: item.token_amount,
              percent: item.token_amount,
              amount: String(item.amount),
              isTreasury: false,
            }
          })
        : splitRevenue(SIMULATED_PRODUCTION.revenue, project, holdings[projectId] ?? {}, profiles)
      const event: ProductionEvent = {
        id: makeId('e'),
        projectId,
        timestamp: new Date().toISOString(),
        ...SIMULATED_PRODUCTION,
        contract_transaction_id: response.contract_transaction_id,
        distribution,
      }
      const deltas: Record<string, number> = {}
      for (const share of distribution) deltas[share.holderId] = (deltas[share.holderId] ?? 0) + Number(share.amount)
      adjustBalances(deltas)
      setProductionHistory((prev) => [event, ...prev])
      setLastProductionEvent(event)
      pushToast({
        variant: 'success',
        title: 'HSCS distribution executed',
        description: `${SIMULATED_PRODUCTION.energy_kwh} kWh → ${formatUSD(Number(SIMULATED_PRODUCTION.revenue))} split to ${distribution.length} holders`,
        txId: response.contract_transaction_id,
      })
    } catch {
      fail('Smart contract execution failed')
    } finally {
      setIsSimulating(false)
    }
  }

  function handleSelectAiProject(projectId: string) {
    setAiProjectId(projectId)
    const project = projects.find((p) => p.id === projectId)
    if (project) setAiRegion(project.region)
  }

  return (
    <div className="min-h-dvh bg-slate-950 text-slate-200">
      <TopNav
        activeTab={activeTab}
        onTabChange={setActiveTab}
        profiles={profiles}
        activeProfile={activeProfile}
        kycRecords={kycRecords}
        onProfileChange={setActiveProfileId}
      />

      <main>
        {activeTab === 'home' && <HomeTab projects={projects} history={productionHistory} onNavigate={setActiveTab} />}
        {activeTab === 'invest' && (
          <InvestTab
            projects={projects}
            profiles={profiles}
            activeProfile={activeProfile}
            kyc={activeKyc}
            holdings={holdings}
            listings={listings}
            pendingBuyProjectId={pendingBuyProjectId}
            pendingListingId={pendingListingId}
            isCreatingListing={isCreatingListing}
            onOpenKyc={() => setIsKycModalOpen(true)}
            onBuyPrimary={handleBuyPrimary}
            onCreateListing={handleCreateListing}
            onBuyListing={handleBuyListing}
            onCancelListing={handleCancelListing}
          />
        )}
        {activeTab === 'owner' && (
          <OwnerTab
            activeProfile={activeProfile}
            profiles={profiles}
            projects={projects}
            holdings={holdings}
            deployState={deployState}
            history={productionHistory}
            lastEvent={lastProductionEvent}
            isSimulating={isSimulating}
            simulatedPayload={SIMULATED_PRODUCTION}
            kycVerified={activeKyc.identityVerified && activeKyc.ownerVerified}
            onDeploy={handleDeployProject}
            onResetDeploy={() => setDeployState({ status: 'idle' })}
            onSimulate={handleSimulateProduction}
          />
        )}
        {activeTab === 'ai' && (
          <AiPredictorTab
            projects={projects}
            projectId={aiProjectId}
            region={aiRegion}
            range={forecastRange}
            onProjectChange={handleSelectAiProject}
            onRegionChange={setAiRegion}
            onRangeChange={setForecastRange}
          />
        )}
      </main>

      <KycModal
        open={isKycModalOpen}
        status={kycStatus}
        defaultUserId={activeProfile.id}
        defaultName={activeProfile.name}
        onClose={() => {
          if (kycStatus !== 'loading') setIsKycModalOpen(false)
        }}
        onSubmit={handleVerifyKyc}
      />
      <ToastStack toasts={toasts} onDismiss={dismissToast} />
    </div>
  )
}
