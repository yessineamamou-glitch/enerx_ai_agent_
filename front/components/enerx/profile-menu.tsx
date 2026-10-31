'use client'

import { Check, ChevronDown, ShieldAlert, ShieldCheck } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import type { KycRecord, Profile } from '@/lib/enerx/types'
import { formatUSD } from '@/lib/enerx/utils'
import { cn } from '@/lib/utils'

interface ProfileMenuProps {
  profiles: Profile[]
  activeProfile: Profile
  kycRecords: Record<string, KycRecord>
  onChange: (id: string) => void
}

function Avatar({ profile }: { profile: Profile }) {
  return (
    <span
      className={cn(
        'flex size-8 shrink-0 items-center justify-center rounded-full font-mono text-xs font-bold',
        'bg-azure/15 text-azure ring-1 ring-azure/40',
      )}
      aria-hidden
    >
      {profile.initials}
    </span>
  )
}

export function ProfileMenu({ profiles, activeProfile, kycRecords, onChange }: ProfileMenuProps) {
  const [open, setOpen] = useState(false)
  const containerRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return
    const onPointer = (e: PointerEvent) => {
      if (!containerRef.current?.contains(e.target as Node)) setOpen(false)
    }
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && setOpen(false)
    document.addEventListener('pointerdown', onPointer)
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('pointerdown', onPointer)
      document.removeEventListener('keydown', onKey)
    }
  }, [open])

  return (
    <div ref={containerRef} className="relative">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-haspopup="menu"
        aria-expanded={open}
        className="flex items-center gap-2.5 rounded-xl border border-white/10 bg-slate-900/80 py-1.5 pr-2.5 pl-1.5 text-left transition hover:border-white/20"
      >
        <Avatar profile={activeProfile} />
        <span className="hidden flex-col leading-tight sm:flex">
          <span className="text-sm font-medium text-white">{activeProfile.name}</span>
          <span className="font-mono text-[11px] text-slate-400">
            {activeProfile.role} · {formatUSD(activeProfile.balance, 0)}
          </span>
        </span>
        <ChevronDown className={cn('size-4 text-slate-400 transition', open && 'rotate-180')} aria-hidden />
      </button>

      {open && (
        <div
          role="menu"
          className="absolute right-0 mt-2 w-80 overflow-hidden rounded-xl border border-white/10 bg-slate-900/95 shadow-2xl backdrop-blur-xl"
        >
          <p className="border-b border-white/10 px-4 py-2.5 font-mono text-[10px] uppercase tracking-[0.2em] text-slate-500">
            Simulated profiles · mock backend
          </p>
          <ul className="p-1.5">
            {profiles.map((profile) => {
              const verified = kycRecords[profile.id]?.verified
              const active = profile.id === activeProfile.id
              return (
                <li key={profile.id}>
                  <button
                    type="button"
                    role="menuitemradio"
                    aria-checked={active}
                    onClick={() => {
                      onChange(profile.id)
                      setOpen(false)
                    }}
                    className={cn(
                      'flex w-full items-center gap-3 rounded-lg px-2.5 py-2.5 text-left transition hover:bg-white/5',
                      active && 'bg-white/[0.06]',
                    )}
                  >
                    <Avatar profile={profile} />
                    <span className="flex min-w-0 flex-1 flex-col">
                      <span className="flex items-center gap-2 text-sm font-medium text-white">
                        {profile.name}
                        <span
                          className={cn(
                            'rounded px-1.5 py-0.5 font-mono text-[10px] uppercase',
                            'bg-azure/10 text-azure',
                          )}
                        >
                          {profile.role}
                        </span>
                      </span>
                      <span className="flex items-center gap-1.5 font-mono text-[11px] text-slate-400">
                        {formatUSD(profile.balance)} ·
                        {verified ? (
                          <span className="flex items-center gap-1 text-ledger">
                            <ShieldCheck className="size-3" aria-hidden /> DID
                          </span>
                        ) : (
                          <span className="flex items-center gap-1 text-amber-400">
                            <ShieldAlert className="size-3" aria-hidden /> No DID
                          </span>
                        )}
                      </span>
                    </span>
                    {active && <Check className="size-4 text-solar" aria-hidden />}
                  </button>
                </li>
              )
            })}
          </ul>
        </div>
      )}
    </div>
  )
}
