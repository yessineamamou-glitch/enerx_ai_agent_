'use client'

import { BrainCircuit, Building2, Home, TrendingUp, Zap } from 'lucide-react'
import type { KycRecord, Profile, TabId } from '@/lib/enerx/types'
import { cn } from '@/lib/utils'
import { ProfileMenu } from './profile-menu'

const TABS: { id: TabId; label: string; icon: typeof Home }[] = [
  { id: 'home', label: 'Home', icon: Home },
  { id: 'invest', label: 'Invest', icon: TrendingUp },
  { id: 'owner', label: 'Operate', icon: Building2 },
  { id: 'ai', label: 'AI Predictor', icon: BrainCircuit },
]

interface TopNavProps {
  activeTab: TabId
  onTabChange: (tab: TabId) => void
  profiles: Profile[]
  activeProfile: Profile
  kycRecords: Record<string, KycRecord>
  onProfileChange: (id: string) => void
}

export function TopNav({ activeTab, onTabChange, profiles, activeProfile, kycRecords, onProfileChange }: TopNavProps) {
  const tabButtons = (compact: boolean) =>
    TABS.map(({ id, label, icon: Icon }) => {
      const active = activeTab === id
      return (
        <button
          key={id}
          type="button"
          onClick={() => onTabChange(id)}
          aria-current={active ? 'page' : undefined}
          className={cn(
            'relative flex shrink-0 items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium transition',
            active
              ? 'bg-white/[0.06] text-white shadow-[inset_0_0_0_1px_rgba(255,102,34,0.4)]'
              : 'text-slate-400 hover:bg-white/[0.04] hover:text-slate-100',
            compact && 'px-2.5 py-1.5 text-xs',
          )}
        >
          <Icon className={cn('size-4', active ? 'text-solar' : 'text-slate-500')} aria-hidden />
          {label}
          {active && (
            <span className="absolute inset-x-3 -bottom-[9px] h-px bg-solar shadow-[0_0_10px_2px_rgba(255,102,34,0.6)]" aria-hidden />
          )}
        </button>
      )
    })

  return (
    <header className="sticky top-0 z-40 border-b border-white/10 bg-slate-950/80 backdrop-blur-xl">
      <div className="mx-auto flex h-16 max-w-7xl items-center gap-4 px-4 md:px-6">
        <button
          type="button"
          onClick={() => onTabChange('home')}
          className="flex items-center gap-2.5"
          aria-label="EnerX home"
        >
          <span className="flex size-9 items-center justify-center rounded-lg bg-solar/15 ring-1 ring-solar/50 shadow-[0_0_20px_rgba(255,102,34,0.35)]">
            <Zap className="size-5 fill-solar text-solar" aria-hidden />
          </span>
          <span className="text-xl font-bold tracking-tight text-white">
            Ener<span className="text-solar">X</span>
          </span>
        </button>

        <nav aria-label="Primary" className="ml-4 hidden items-center gap-1 md:flex">
          {tabButtons(false)}
        </nav>

        <div className="ml-auto flex items-center gap-3">
          <span className="hidden items-center gap-2 rounded-full border border-ledger/40 bg-ledger/10 px-3 py-1 font-mono text-[11px] font-semibold tracking-wider text-ledger sm:flex">
            <span className="relative flex size-2">
              <span className="absolute inline-flex size-full animate-ping rounded-full bg-ledger opacity-75" />
              <span className="relative inline-flex size-2 rounded-full bg-ledger" />
            </span>
            HEDERA TESTNET
          </span>
          <ProfileMenu
            profiles={profiles}
            activeProfile={activeProfile}
            kycRecords={kycRecords}
            onChange={onProfileChange}
          />
        </div>
      </div>
      <nav aria-label="Primary mobile" className="flex gap-1 overflow-x-auto border-t border-white/5 px-3 py-2 md:hidden">
        {tabButtons(true)}
      </nav>
    </header>
  )
}
