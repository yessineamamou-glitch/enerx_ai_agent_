export type TabId = 'home' | 'invest' | 'owner' | 'ai'

export type Role = 'Participant'

export type Region = 'Tunis' | 'Sfax' | 'Tozeur' | 'Djerba'

export type ForecastRange = '7d' | '14d'

export interface Profile {
  id: string
  backendId?: number
  name: string
  role: Role
  balance: number
  initials: string
  hederaAccount: string
}

export interface KycRecord {
  verified: boolean
  did: string | null
  identityVerified: boolean
  investorVerified: boolean
  ownerVerified: boolean
  legalName?: string
  email?: string
}

export interface Project {
  id: string
  backendId?: number
  backendTokenId?: number
  name: string
  location: string
  region: Region
  description: string
  targetFunding: number
  tokenName: string
  tokenSymbol: string
  hederaTokenId: string
  ownerId: string
  totalSupply: number
  ownerRetained: number
  availableTokens: number
  capacityKwp: number
}

/** holdings[projectId][profileId] = token count */
export type Holdings = Record<string, Record<string, number>>

export interface Listing {
  id: string
  projectId: string
  sellerId: string
  amount: number
  unitPrice: number
}

export interface DistributionShare {
  holderId: string
  label: string
  tokens: number
  percent: number
  amount: string
  isTreasury: boolean
}

export interface ProductionEvent {
  id: string
  projectId: string
  timestamp: string
  energy_kwh: string
  revenue: string
  contract_transaction_id: string
  distribution: DistributionShare[]
}

export interface Toast {
  id: string
  variant: 'success' | 'error' | 'info'
  title: string
  description?: string
  txId?: string
}

export interface KycSubmission {
  userId: string
  legalName: string
  email: string
}

export interface NewProjectInput {
  name: string
  description: string
  targetFunding: number
  tokenName: string
  tokenSymbol: string
  region: Region
  capacityKwp: number
}

export type DeployState =
  | { status: 'idle' }
  | { status: 'deploying'; step: number }
  | { status: 'success'; tokenId: string; projectName: string; symbol: string }
  | { status: 'error'; message: string }
