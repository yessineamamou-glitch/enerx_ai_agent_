import type { AiReport } from './ai-api'
import type { ForecastRange, Region } from './types'
import { OWNER_RETAINED, TOTAL_SUPPLY } from './utils'

export const REGIONS: Region[] = ['Tunis', 'Sfax', 'Tozeur', 'Djerba']

/** Position sent to the AI model for each region (city centres). */
export const REGION_COORDS: Record<Region, { lat: number; lon: number }> = {
  Tunis: { lat: 36.8, lon: 10.18 },
  Sfax: { lat: 34.74, lon: 10.76 },
  Tozeur: { lat: 33.92, lon: 8.13 },
  Djerba: { lat: 33.81, lon: 10.86 },
}

export const RANGE_DAYS: Record<ForecastRange, number> = { '7d': 7, '14d': 14 }

/** Revenue depends ONLY on forecast production x STEG tariff. News never enter the calculation. */
export const OWNER_SHARE = OWNER_RETAINED / TOTAL_SUPPLY

export type Currency = 'USDC' | 'DT' | 'USD'

export interface ForecastPoint {
  label: string
  temperature: number
  irradiance: number // kWh/m²/day
  projected: number // kWh
  low: number
  high: number
  ownerRevenue: number
  investorRevenue: number
}

export interface ForecastResult {
  points: ForecastPoint[]
  currency: Currency
  totalKwh: number
  totalRevenue: number
  tariffLabel: string
  reportHash?: string
  warnings: string[]
  source: 'model' | 'simulated'
}

export function fromReport(report: AiReport): ForecastResult {
  const usdc = report.totals.revenue_usdc !== undefined
  const points = report.days.map((d) => {
    const revenue = usdc ? (d.revenue_usdc ?? 0) : d.revenue_dt
    return {
      label: d.date.slice(5),
      temperature: d.temperature_c,
      irradiance: Number((d.irradiance_wh_m2 / 1000).toFixed(2)),
      projected: Math.round(d.kwh),
      low: Math.round(d.kwh_low),
      high: Math.round(d.kwh_high),
      ownerRevenue: Number((revenue * OWNER_SHARE).toFixed(2)),
      investorRevenue: Number((revenue * (1 - OWNER_SHARE)).toFixed(2)),
    }
  })
  return {
    points,
    currency: usdc ? 'USDC' : 'DT',
    totalKwh: report.totals.kwh,
    totalRevenue: usdc ? (report.totals.revenue_usdc ?? 0) : report.totals.revenue_dt,
    tariffLabel: `${report.assumptions.tariff_dt_per_kwh} DT/kWh`,
    reportHash: report.report_hash,
    warnings: report.warnings ?? [],
    source: 'model',
  }
}

// ---------------------------------------------------------------------------
// Offline fallback (used only when the AI service cannot be reached)
// ---------------------------------------------------------------------------
const REGION_PROFILE: Record<Region, { yield: number; cloud: number }> = {
  Tunis: { yield: 1, cloud: 34 },
  Sfax: { yield: 1.08, cloud: 26 },
  Tozeur: { yield: 1.22, cloud: 11 },
  Djerba: { yield: 1.13, cloud: 21 },
}
const FALLBACK_TARIFF_USD = 0.2
const noise = (i: number, seed: number) => {
  const x = Math.sin(i * 12.9898 + seed * 78.233) * 43758.5453
  return x - Math.floor(x)
}

export function buildFallbackForecast(capacityKwp: number, region: Region, range: ForecastRange): ForecastResult {
  const profile = REGION_PROFILE[region]
  const seed = REGIONS.indexOf(region) * 13 + capacityKwp
  const today = new Date()
  const points = Array.from({ length: RANGE_DAYS[range] }, (_, i) => {
    const cloud = Math.min(88, Math.max(2, profile.cloud * (0.45 + noise(i, seed) * 1.1)))
    const projected = capacityKwp * 0.62 * profile.yield * 0.88 * (1 - cloud / 220) * 8
    const revenue = projected * FALLBACK_TARIFF_USD
    const d = new Date(today.getTime() + i * 86_400_000)
    return {
      label: d.toISOString().slice(5, 10),
      temperature: Number((22 + noise(i, seed + 3) * 8).toFixed(1)),
      irradiance: Number((6.4 * profile.yield * 0.88 * (1 - cloud / 160)).toFixed(2)),
      projected: Math.round(projected),
      low: Math.round(projected * 0.88),
      high: Math.round(projected * 1.12),
      ownerRevenue: Number((revenue * OWNER_SHARE).toFixed(2)),
      investorRevenue: Number((revenue * (1 - OWNER_SHARE)).toFixed(2)),
    }
  })
  return {
    points,
    currency: 'USD',
    totalKwh: points.reduce((s, p) => s + p.projected, 0),
    totalRevenue: points.reduce((s, p) => s + p.ownerRevenue + p.investorRevenue, 0),
    tariffLabel: `${FALLBACK_TARIFF_USD} USD/kWh`,
    warnings: [],
    source: 'simulated',
  }
}

// ---------------------------------------------------------------------------
// Return metrics (linear annualisation of the forecast window)
// ---------------------------------------------------------------------------
export function computeSummary(result: ForecastResult, days: number, targetFunding: number) {
  const annualRevenue = (result.totalRevenue / days) * 365
  const comparable = result.currency !== 'DT' // target funding is in USD: only compare USD-like amounts
  return {
    annualRevenue,
    roiPercent: comparable ? (annualRevenue / targetFunding) * 100 : null,
    perTokenYield: annualRevenue / TOTAL_SUPPLY,
    paybackYears: comparable ? targetFunding / annualRevenue : null,
    ownerPool: result.totalRevenue * OWNER_SHARE,
    investorPool: result.totalRevenue * (1 - OWNER_SHARE),
  }
}

export function formatMoney(value: number, currency: Currency, digits = 2) {
  const n = new Intl.NumberFormat('en-US', { minimumFractionDigits: digits, maximumFractionDigits: digits }).format(value)
  return currency === 'DT' ? `${n} DT` : currency === 'USDC' ? `${n} USDC` : `$${n}`
}
