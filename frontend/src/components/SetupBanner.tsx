/**
 * SetupBanner — shown at the top of the chat when Gmail or bank account
 * aren't connected yet. Dismissable per session; re-appears next reload
 * until both are connected.
 */
import { useEffect, useState } from 'react'
import { AlertCircle, X, CreditCard, Mail } from 'lucide-react'
import { apiFetch } from '@/lib/api'

interface SetupStatus {
  google: boolean
  plaid: boolean
}

interface SetupBannerProps {
  onGoToSettings: () => void
}

export function SetupBanner({ onGoToSettings }: SetupBannerProps) {
  const [status, setStatus] = useState<SetupStatus | null>(null)
  const [dismissed, setDismissed] = useState(false)

  useEffect(() => {
    let cancelled = false
    async function check() {
      try {
        const [google, plaid] = await Promise.all([
          apiFetch('/api/auth/google/status').then((d: { connected: boolean }) => d.connected).catch(() => false),
          apiFetch('/api/plaid/items').then((d: { items: unknown[] }) => d.items.length > 0).catch(() => false),
        ])
        if (!cancelled) setStatus({ google: google as boolean, plaid: plaid as boolean })
      } catch {
        if (!cancelled) setStatus({ google: false, plaid: false })
      }
    }
    void check()
    return () => { cancelled = true }
  }, [])

  if (dismissed) return null
  if (!status) return null
  if (status.google && status.plaid) return null  // all connected — nothing to show

  const missing: { icon: React.ReactNode; label: string; detail: string }[] = []
  if (!status.google) missing.push({
    icon: <Mail size={13} className="text-blue-500 shrink-0 mt-0.5" />,
    label: 'Gmail & Calendar',
    detail: 'Meetings and email in chat',
  })
  if (!status.plaid) missing.push({
    icon: <CreditCard size={13} className="text-emerald-500 shrink-0 mt-0.5" />,
    label: 'Bank account',
    detail: 'Spending and subscriptions in chat',
  })

  return (
    <div className="mb-4 bg-amber-50 border border-amber-200 rounded-2xl p-3.5 relative">
      <button
        onClick={() => setDismissed(true)}
        className="absolute top-2.5 right-2.5 p-1 rounded-lg text-amber-400 active:text-amber-600 transition"
        aria-label="Dismiss"
      >
        <X size={14} />
      </button>

      <div className="flex items-start gap-2 pr-6">
        <AlertCircle size={15} className="text-amber-500 shrink-0 mt-0.5" />
        <div className="space-y-2 flex-1">
          <p className="text-xs font-semibold text-amber-800">
            Finish setup
          </p>

          <div className="space-y-1.5">
            {missing.map((item) => (
              <div key={item.label} className="flex items-start gap-1.5">
                {item.icon}
                <div>
                  <span className="text-xs font-medium text-paper-700">{item.label}</span>
                  <span className="text-[11px] text-paper-500 ml-1">— {item.detail}</span>
                </div>
              </div>
            ))}
          </div>

          <button
            onClick={onGoToSettings}
            className="text-xs font-semibold text-amber-700 bg-amber-100 active:bg-amber-200 px-3 py-1.5 rounded-lg transition mt-1"
          >
            Connect now →
          </button>
        </div>
      </div>
    </div>
  )
}
