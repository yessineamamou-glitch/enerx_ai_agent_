import type { DistributionShare, Profile, Project } from './types'

export const TOTAL_SUPPLY = 100
export const OWNER_RETAINED = 30
export const INVESTOR_ALLOCATION = TOTAL_SUPPLY - OWNER_RETAINED

export const DEPLOY_STEPS = [
  'Compiling HTS token schema (0 decimals)',
  'Submitting TokenCreateTransaction',
  'Awaiting hashgraph consensus',
  `Minting ${TOTAL_SUPPLY} fungible units`,
  `Associating treasury · ${OWNER_RETAINED} tokens retained`,
]

export const tokenPrice = (project: Project) => project.targetFunding / INVESTOR_ALLOCATION

export const collectedFunding = (project: Project) =>
  (INVESTOR_ALLOCATION - project.availableTokens) * tokenPrice(project)

export function formatUSD(value: number, digits = 2) {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  }).format(value)
}

export function formatNumber(value: number, digits = 0) {
  return new Intl.NumberFormat('en-US', {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  }).format(value)
}

export function formatTimestamp(iso: string) {
  return `${iso.slice(0, 10)} ${iso.slice(11, 19)} UTC`
}

const randomDigits = (length: number) =>
  Array.from({ length }, () => Math.floor(Math.random() * 10)).join('')

export const makeHtsTxId = () => `0.0.384@${Math.floor(Date.now() / 1000)}.${randomDigits(9)}`
export const makeContractTxId = () =>
  `0.0.5123408@${Math.floor(Date.now() / 1000)}.${randomDigits(9)}`
export const makeTokenId = () => `0.0.${4_800_000 + Math.floor(Math.random() * 199_999)}`
export const makeDid = (accountId: string) =>
  `did:hedera:testnet:z6Mk${Math.random().toString(36).slice(2, 12)}${Math.random()
    .toString(36)
    .slice(2, 10)}_${accountId}`
export const makeId = (prefix: string) => `${prefix}-${Math.random().toString(36).slice(2, 10)}`

/**
 * Splits a decimal revenue string across token holders using integer cents so the
 * shares always sum exactly to the revenue. Unsold tokens accrue to the owner treasury.
 */
export function splitRevenue(
  revenue: string,
  project: Project,
  projectHoldings: Record<string, number>,
  profiles: Profile[],
): DistributionShare[] {
  const totalCents = Math.round(Number(revenue) * 100)
  const rows = Object.entries(projectHoldings)
    .filter(([, tokens]) => tokens > 0)
    .map(([holderId, tokens]) => ({
      holderId,
      label: profiles.find((p) => p.id === holderId)?.name ?? holderId,
      tokens,
      isTreasury: false,
    }))

  if (project.availableTokens > 0) {
    rows.push({
      holderId: project.ownerId,
      label: 'Unsold pool · Owner treasury',
      tokens: project.availableTokens,
      isTreasury: true,
    })
  }

  const cents = rows.map((row) => Math.floor((totalCents * row.tokens) / project.totalSupply))
  const remainder = totalCents - cents.reduce((sum, c) => sum + c, 0)
  const ownerIndex = rows.findIndex((row) => row.holderId === project.ownerId)
  if (rows.length > 0) cents[ownerIndex >= 0 ? ownerIndex : 0] += remainder

  return rows.map((row, i) => ({
    ...row,
    percent: (row.tokens / project.totalSupply) * 100,
    amount: (cents[i] / 100).toFixed(2),
  }))
}
