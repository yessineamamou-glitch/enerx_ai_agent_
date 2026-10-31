'use client'

import { AlertTriangle, CheckCircle2, Info, X } from 'lucide-react'
import type { Toast } from '@/lib/enerx/types'
import { cn } from '@/lib/utils'

const VARIANT_STYLES = {
  success: {
    icon: CheckCircle2,
    container: 'border-ledger/50 shadow-[0_0_40px_-8px_rgba(52,211,153,0.55)]',
    icon_: 'text-ledger',
    bar: 'bg-ledger',
  },
  error: {
    icon: AlertTriangle,
    container: 'border-rose-500/50 shadow-[0_0_40px_-8px_rgba(244,63,94,0.5)]',
    icon_: 'text-rose-400',
    bar: 'bg-rose-500',
  },
  info: {
    icon: Info,
    container: 'border-azure/50 shadow-[0_0_40px_-8px_rgba(34,211,238,0.45)]',
    icon_: 'text-azure',
    bar: 'bg-azure',
  },
} as const

export function ToastStack({ toasts, onDismiss }: { toasts: Toast[]; onDismiss: (id: string) => void }) {
  return (
    <div
      aria-live="polite"
      className="pointer-events-none fixed inset-x-4 top-20 z-50 flex flex-col items-end gap-3 sm:left-auto sm:right-6 sm:w-[26rem]"
    >
      {toasts.map((toast) => {
        const styles = VARIANT_STYLES[toast.variant]
        const Icon = styles.icon
        return (
          <div
            key={toast.id}
            role={toast.variant === 'error' ? 'alert' : 'status'}
            className={cn(
              'pointer-events-auto relative w-full overflow-hidden rounded-xl border bg-slate-900/95 p-4 backdrop-blur-xl animate-in slide-in-from-right-8 fade-in duration-300',
              styles.container,
            )}
          >
            <span className={cn('absolute inset-y-0 left-0 w-1', styles.bar)} aria-hidden />
            <div className="flex items-start gap-3 pl-1">
              <Icon className={cn('mt-0.5 size-5 shrink-0', styles.icon_)} aria-hidden />
              <div className="min-w-0 flex-1">
                <p className="text-sm font-semibold text-white">{toast.title}</p>
                {toast.description && <p className="mt-0.5 text-xs leading-relaxed text-slate-400">{toast.description}</p>}
                {toast.txId && (
                  <p className="mt-2 break-all rounded-md border border-white/10 bg-slate-950/80 px-2 py-1.5 font-mono text-[11px] text-slate-300">
                    [Tx ID: <span className={styles.icon_}>{toast.txId}</span>]
                  </p>
                )}
              </div>
              <button
                type="button"
                onClick={() => onDismiss(toast.id)}
                className="rounded p-1 text-slate-500 transition hover:bg-white/5 hover:text-slate-200"
                aria-label="Dismiss notification"
              >
                <X className="size-4" aria-hidden />
              </button>
            </div>
          </div>
        )
      })}
    </div>
  )
}
