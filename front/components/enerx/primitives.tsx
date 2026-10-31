import type { ReactNode } from 'react'
import { cn } from '@/lib/utils'

export const inputClass =
  'w-full rounded-lg border border-white/10 bg-slate-950/70 px-3 py-2.5 text-sm text-slate-100 placeholder:text-slate-500 outline-none transition focus:border-solar/70 focus:ring-2 focus:ring-solar/30 disabled:opacity-50'

export const labelClass = 'mb-1.5 block font-mono text-[11px] uppercase tracking-wider text-slate-400'

export function Panel({ className, children }: { className?: string; children: ReactNode }) {
  return (
    <div
      className={cn(
        'rounded-2xl border border-white/10 bg-slate-900/70 shadow-[0_0_0_1px_rgba(255,255,255,0.02),0_20px_60px_-30px_rgba(0,0,0,0.8)] backdrop-blur',
        className,
      )}
    >
      {children}
    </div>
  )
}

export function SectionHeader({
  eyebrow,
  title,
  description,
  action,
}: {
  eyebrow: string
  title: string
  description?: string
  action?: ReactNode
}) {
  return (
    <div className="flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
      <div>
        <p className="font-mono text-xs uppercase tracking-[0.2em] text-azure">{eyebrow}</p>
        <h2 className="mt-2 text-balance text-3xl font-semibold tracking-tight text-white md:text-4xl">{title}</h2>
        {description && <p className="mt-2 max-w-2xl text-pretty text-sm leading-relaxed text-slate-400">{description}</p>}
      </div>
      {action}
    </div>
  )
}

export function Spinner({ className }: { className?: string }) {
  return (
    <span
      aria-hidden
      className={cn('inline-block size-4 animate-spin rounded-full border-2 border-current border-t-transparent', className)}
    />
  )
}

export function ProgressBar({ value, className, barClassName }: { value: number; className?: string; barClassName?: string }) {
  return (
    <div className={cn('h-2 w-full overflow-hidden rounded-full bg-slate-800', className)}>
      <div
        className={cn('h-full rounded-full bg-solar shadow-[0_0_12px_rgba(255,102,34,0.6)] transition-all duration-700', barClassName)}
        style={{ width: `${Math.min(100, Math.max(0, value))}%` }}
      />
    </div>
  )
}
