'use client'

import { Fingerprint, X } from 'lucide-react'
import { useEffect, useState, type FormEvent } from 'react'
import type { KycSubmission } from '@/lib/enerx/types'
import { Spinner, inputClass, labelClass } from '../primitives'

interface KycModalProps {
  open: boolean
  status: 'idle' | 'loading' | 'pending' | 'error'
  defaultUserId: string
  defaultName: string
  onClose: () => void
  onSubmit: (submission: KycSubmission) => void
}

export function KycModal({ open, status, defaultUserId, defaultName, onClose, onSubmit }: KycModalProps) {
  if (!open) return null
  return (
    <KycModalContent
      key={defaultUserId}
      status={status}
      defaultUserId={defaultUserId}
      defaultName={defaultName}
      onClose={onClose}
      onSubmit={onSubmit}
    />
  )
}

function KycModalContent({ status, defaultUserId, defaultName, onClose, onSubmit }: Omit<KycModalProps, 'open'>) {
  const [userId, setUserId] = useState(defaultUserId)
  const [legalName, setLegalName] = useState(defaultName)
  const [email, setEmail] = useState('')
  const loading = status === 'loading'

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onClose()
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [onClose])

  function handleSubmit(e: FormEvent) {
    e.preventDefault()
    onSubmit({ userId: userId.trim(), legalName: legalName.trim(), email: email.trim() })
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <button
        type="button"
        aria-label="Close dialog"
        className="absolute inset-0 bg-slate-950/80 backdrop-blur-sm"
        onClick={onClose}
      />
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="kyc-title"
        className="relative w-full max-w-md overflow-hidden rounded-2xl border border-azure/30 bg-slate-900 shadow-[0_0_80px_-20px_rgba(34,211,238,0.6)] animate-in zoom-in-95 fade-in duration-200"
      >
        <div className="flex items-start justify-between border-b border-white/10 p-5">
          <div className="flex items-center gap-3">
            <span className="flex size-10 items-center justify-center rounded-lg bg-azure/10 ring-1 ring-azure/40">
              <Fingerprint className="size-5 text-azure" aria-hidden />
            </span>
            <div>
              <h2 id="kyc-title" className="font-semibold text-white">
                Decentralized Identity (DID) KYC
              </h2>
              <p className="font-mono text-[11px] text-slate-400">Hedera DID service · participant credential verification</p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            disabled={loading}
            className="rounded p-1 text-slate-500 hover:bg-white/5 hover:text-white disabled:opacity-40"
            aria-label="Close"
          >
            <X className="size-4" />
          </button>
        </div>

        {loading ? (
          <div className="flex flex-col items-center gap-5 px-6 py-12" role="status">
            <div className="relative flex size-24 items-center justify-center overflow-hidden rounded-2xl border border-azure/40 bg-slate-950">
              <Fingerprint className="size-12 text-azure/70" aria-hidden />
              <span
                className="absolute inset-x-0 top-0 h-6 bg-gradient-to-b from-transparent via-azure/50 to-transparent"
                style={{ animation: 'enerx-scan 1.4s linear infinite' }}
                aria-hidden
              />
            </div>
            <div className="text-center">
              <p className="font-semibold text-white">Running HCS identity lookup…</p>
              <p className="mt-1 font-mono text-xs text-slate-400">Creating or resolving your DID and checking its verification status</p>
            </div>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="flex flex-col gap-4 p-5">
            <div>
              <label htmlFor="kyc-user-id" className={labelClass}>
                User ID
              </label>
              <input id="kyc-user-id" required value={userId} onChange={(e) => setUserId(e.target.value)} className={`${inputClass} font-mono`} />
            </div>
            <div>
              <label htmlFor="kyc-name" className={labelClass}>
                Legal name
              </label>
              <input
                id="kyc-name"
                required
                autoComplete="name"
                value={legalName}
                onChange={(e) => setLegalName(e.target.value)}
                className={inputClass}
              />
            </div>
            <div>
              <label htmlFor="kyc-email" className={labelClass}>
                Email
              </label>
              <input
                id="kyc-email"
                type="email"
                required
                autoComplete="email"
                placeholder="you@example.tn"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className={inputClass}
              />
            </div>
            {status === 'error' && (
              <p role="alert" className="rounded-lg border border-rose-500/40 bg-rose-500/10 px-3 py-2 text-xs text-rose-300">
                Verification failed. Please try again.
              </p>
            )}
            {status === 'pending' && (
              <p role="status" className="rounded-lg border border-amber-400/40 bg-amber-400/10 px-3 py-2 text-xs text-amber-200">
                Your DID exists, but a participant credential has not been issued yet. Refresh after the issuer validates your documents.
              </p>
            )}
            <button
              type="submit"
              className="mt-1 inline-flex items-center justify-center gap-2 rounded-lg bg-solar px-4 py-2.5 text-sm font-semibold text-slate-950 transition hover:brightness-110"
            >
              {loading && <Spinner />} {status === 'pending' ? 'Refresh verification status' : 'Verify identity on Hedera'}
            </button>
            <p className="text-center font-mono text-[10px] text-slate-500">Identity details are sent securely to the EnerX verification service</p>
          </form>
        )}
      </div>
    </div>
  )
}
