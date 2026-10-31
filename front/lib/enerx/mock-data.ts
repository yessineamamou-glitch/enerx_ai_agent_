import type { Holdings, KycRecord, Listing, ProductionEvent, Profile, Project } from './types'
import { OWNER_RETAINED, TOTAL_SUPPLY, splitRevenue } from './utils'

export const INITIAL_PROFILES: Profile[] = [
  { id: 'owner-1', backendId: 1, name: 'Rayen Segni', role: 'Participant', balance: 12000, initials: 'RS', hederaAccount: '0.0.10652075' },
  { id: 'investor-1', backendId: 2, name: 'Amen Beji', role: 'Participant', balance: 25000, initials: 'AB', hederaAccount: '0.0.10794965' },
  { id: 'investor-2', backendId: 3, name: 'Yassine Ammamo', role: 'Participant', balance: 18000, initials: 'YA', hederaAccount: '0.0.10872211' },
]

export const INITIAL_KYC: Record<string, KycRecord> = {
  'owner-1': {
    verified: false,
    did: null,
    identityVerified: false,
    investorVerified: false,
    ownerVerified: false,
    legalName: 'Rayen Segni',
  },
  'investor-1': {
    verified: false,
    did: null,
    identityVerified: false,
    investorVerified: false,
    ownerVerified: false,
  },
  'investor-2': {
    verified: false,
    did: null,
    identityVerified: false,
    investorVerified: false,
    ownerVerified: false,
    legalName: 'Yassine Ammamo',
  },
}

const baseProject = { ownerId: 'owner-1', totalSupply: TOTAL_SUPPLY, ownerRetained: OWNER_RETAINED }

export const INITIAL_PROJECTS: Project[] = [
  {
    ...baseProject,
    id: 'p-sbs',
    name: 'Sidi Bou Saïd Rooftop Array',
    location: 'Sidi Bou Saïd, Tunis',
    region: 'Tunis',
    description: '48 kWp distributed across 22 whitewashed rooftops, injecting into the STEG grid during evening peak.',
    targetFunding: 84000,
    tokenName: 'Sidi Bou Said Solar',
    tokenSymbol: 'SBS',
    hederaTokenId: '0.0.4821937',
    availableTokens: 0,
    capacityKwp: 48,
  },
  {
    ...baseProject,
    id: 'p-hsm',
    name: 'Houmt Souk Microgrid',
    location: 'Houmt Souk, Djerba',
    region: 'Djerba',
    description: 'Island microgrid with battery buffering to offset summer tourism demand spikes.',
    targetFunding: 49000,
    tokenName: 'Houmt Souk Energy',
    tokenSymbol: 'HSM',
    hederaTokenId: '0.0.4822104',
    availableTokens: 46,
    capacityKwp: 32,
  },
  {
    ...baseProject,
    id: 'p-tzo',
    name: 'Tozeur Oasis Canopy',
    location: 'Tozeur Oasis',
    region: 'Tozeur',
    description: 'High-irradiance desert canopy shading palm groves while feeding the southern STEG feeder.',
    targetFunding: 126000,
    tokenName: 'Tozeur Oasis Power',
    tokenSymbol: 'TZO',
    hederaTokenId: '0.0.4823550',
    availableTokens: 70,
    capacityKwp: 72,
  },
  {
    ...baseProject,
    id: 'p-sfx',
    name: 'Sfax Medina Rooftops',
    location: 'Medina, Sfax',
    region: 'Sfax',
    description: 'Retrofit of historic medina rooftops with low-profile bifacial modules.',
    targetFunding: 56000,
    tokenName: 'Sfax Medina Solar',
    tokenSymbol: 'SFX',
    hederaTokenId: '0.0.4824012',
    availableTokens: 58,
    capacityKwp: 36,
  },
]

export const INITIAL_HOLDINGS: Holdings = {
  'p-sbs': { 'owner-1': 30, 'investor-1': 40, 'investor-2': 30 },
  'p-hsm': { 'owner-1': 30, 'investor-2': 24 },
  'p-tzo': { 'owner-1': 30 },
  'p-sfx': { 'owner-1': 30, 'investor-1': 12 },
}

export const INITIAL_LISTINGS: Listing[] = [
  { id: 'l-1', projectId: 'p-sbs', sellerId: 'investor-2', amount: 5, unitPrice: 1290 },
  { id: 'l-2', projectId: 'p-sfx', sellerId: 'investor-1', amount: 4, unitPrice: 860 },
]

const seedEvent = (id: string, timestamp: string, txId: string): ProductionEvent => ({
  id,
  projectId: 'p-sbs',
  timestamp,
  energy_kwh: '520.00',
  revenue: '104.00',
  contract_transaction_id: txId,
  distribution: splitRevenue('104.00', INITIAL_PROJECTS[0], INITIAL_HOLDINGS['p-sbs'], INITIAL_PROFILES),
})

export const INITIAL_HISTORY: ProductionEvent[] = [
  seedEvent('e-2', '2026-10-10T18:00:00Z', '0.0.5123408@1791655200.418220931'),
  seedEvent('e-1', '2026-10-09T18:00:00Z', '0.0.5123408@1791568800.902117345'),
]
