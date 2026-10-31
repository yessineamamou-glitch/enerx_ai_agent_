'use client'

import {
  Area,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ComposedChart,
  Legend,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import type { ForecastPoint } from '@/lib/enerx/forecast'
import type { Region } from '@/lib/enerx/types'

const COLORS = { solar: '#ff6622', azure: '#22d3ee', ledger: '#34d399', violet: '#a78bfa', grid: 'rgba(148,163,184,0.12)', axis: '#64748b' }

const tooltipStyle = {
  contentStyle: {
    background: 'rgba(2,6,23,0.95)',
    border: '1px solid rgba(255,255,255,0.12)',
    borderRadius: 10,
    fontSize: 12,
    fontFamily: 'var(--font-jetbrains-mono)',
  },
  labelStyle: { color: '#e2e8f0', marginBottom: 4 },
  cursor: { fill: 'rgba(255,255,255,0.04)', stroke: 'rgba(255,255,255,0.15)' },
}

const axisProps = {
  stroke: COLORS.axis,
  tick: { fill: COLORS.axis, fontSize: 11 },
  tickLine: false,
  axisLine: false,
}

const legendProps = { wrapperStyle: { fontSize: 12, color: '#94a3b8', paddingTop: 8 } }

export function EnergyChart({ data }: { data: ForecastPoint[] }) {
  return (
    <div className="h-80 w-full lg:h-[27rem]">
      <ResponsiveContainer width="100%" height="100%">
        <ComposedChart data={data} margin={{ top: 8, right: 8, left: -8, bottom: 0 }}>
          <defs>
            <linearGradient id="projGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={COLORS.solar} stopOpacity={0.45} />
              <stop offset="100%" stopColor={COLORS.solar} stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid stroke={COLORS.grid} vertical={false} />
          <XAxis dataKey="label" {...axisProps} minTickGap={12} />
          <YAxis
            {...axisProps}
            width={56}
            domain={[(min: number) => Math.max(0, Math.floor(min * 0.8)), (max: number) => Math.ceil(max * 1.05)]}
          />
          <Tooltip {...tooltipStyle} formatter={(v) => `${Number(v).toLocaleString('en-US')} kWh`} />
          <Legend {...legendProps} />
          <Area
            type="monotone"
            dataKey="projected"
            name="AI projected output (kWh)"
            stroke={COLORS.solar}
            strokeWidth={2.5}
            fill="url(#projGrad)"
            animationDuration={500}
          />
          <Line type="monotone" dataKey="high" name="High (80% range)" stroke={COLORS.azure} strokeWidth={1.5} strokeDasharray="5 4" dot={false} />
          <Line type="monotone" dataKey="low" name="Low (80% range)" stroke={COLORS.azure} strokeWidth={1.5} strokeDasharray="2 4" dot={false} />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  )
}

export function IrradianceChart({ data }: { data: ForecastPoint[] }) {
  return (
    <div className="h-72 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <ComposedChart data={data} margin={{ top: 8, right: 0, left: -16, bottom: 0 }}>
          <CartesianGrid stroke={COLORS.grid} vertical={false} />
          <XAxis dataKey="label" {...axisProps} minTickGap={12} />
          <YAxis yAxisId="irr" {...axisProps} />
          <YAxis yAxisId="temp" orientation="right" {...axisProps} unit="°" />
          <Tooltip {...tooltipStyle} />
          <Legend {...legendProps} />
          <Bar yAxisId="irr" dataKey="irradiance" name="Irradiance (kWh/m²)" fill={COLORS.solar} fillOpacity={0.75} radius={[4, 4, 0, 0]} maxBarSize={22} />
          <Line yAxisId="temp" type="monotone" dataKey="temperature" name="Temperature (°C)" stroke={COLORS.azure} strokeWidth={2} dot={false} />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  )
}

export function RevenueSplitChart({ data, unit = '$' }: { data: ForecastPoint[]; unit?: string }) {
  return (
    <div className="h-72 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} margin={{ top: 8, right: 8, left: -8, bottom: 0 }}>
          <CartesianGrid stroke={COLORS.grid} vertical={false} />
          <XAxis dataKey="label" {...axisProps} minTickGap={12} />
          <YAxis {...axisProps} width={56} />
          <Tooltip {...tooltipStyle} formatter={(v) => `${Number(v).toFixed(2)} ${unit}`} />
          <Legend {...legendProps} />
          <Bar dataKey="ownerRevenue" name="Owner (30%)" stackId="rev" fill={COLORS.azure} maxBarSize={28} />
          <Bar dataKey="investorRevenue" name="Investors (70%)" stackId="rev" fill={COLORS.ledger} radius={[4, 4, 0, 0]} maxBarSize={28} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}

export function RegionChart({
  data,
  activeRegion,
  onSelect,
}: {
  data: { region: Region; projected: number }[]
  activeRegion: Region
  onSelect: (region: Region) => void
}) {
  return (
    <div className="h-64 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} layout="vertical" margin={{ top: 0, right: 16, left: 8, bottom: 0 }}>
          <CartesianGrid stroke={COLORS.grid} horizontal={false} />
          <XAxis type="number" {...axisProps} />
          <YAxis type="category" dataKey="region" {...axisProps} width={64} />
          <Tooltip {...tooltipStyle} formatter={(v) => `${Number(v).toLocaleString('en-US')} kWh over the window`} />
          <Bar
            dataKey="projected"
            name="Projected output"
            radius={[0, 6, 6, 0]}
            maxBarSize={28}
            onClick={(entry) => onSelect((entry as unknown as { region: Region }).region)}
            className="cursor-pointer"
          >
            {data.map((d) => (
              <Cell key={d.region} fill={d.region === activeRegion ? COLORS.solar : 'rgba(34,211,238,0.35)'} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}
