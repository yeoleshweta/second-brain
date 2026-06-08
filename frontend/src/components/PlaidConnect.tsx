import { useCallback, useEffect, useState } from 'react'
import { usePlaidLink } from 'react-plaid-link'
import { Landmark, Loader2, Unlink } from 'lucide-react'
import {
  getPlaidLinkToken,
  getPlaidStatus,
  plaidExchange,
  unlinkPlaidItem,
  type PlaidStatus,
} from '@/lib/api'

function formatLinkedAt(iso: string): string {
  try {
    return new Date(iso).toLocaleDateString(undefined, {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
    })
  } catch {
    return iso
  }
}

export function PlaidConnectSection() {
  const [status, setStatus] = useState<PlaidStatus | null>(null)
  const [linkToken, setLinkToken] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [connecting, setConnecting] = useState(false)
  const [unlinkingId, setUnlinkingId] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [message, setMessage] = useState<string | null>(null)

  const refreshStatus = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const next = await getPlaidStatus()
      setStatus(next)
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void refreshStatus()
  }, [refreshStatus])

  const onSuccess = useCallback(
    async (publicToken: string) => {
      setConnecting(true)
      setError(null)
      setMessage(null)
      try {
        const result = await plaidExchange(publicToken)
        setMessage(`Connected ${result.item.institution_name}`)
        setLinkToken(null)
        await refreshStatus()
      } catch (e) {
        setError((e as Error).message)
      } finally {
        setConnecting(false)
      }
    },
    [refreshStatus],
  )

  const { open, ready } = usePlaidLink({
    token: linkToken,
    onSuccess: (public_token) => void onSuccess(public_token),
    onExit: () => {
      setLinkToken(null)
      setConnecting(false)
    },
  })

  useEffect(() => {
    if (linkToken && ready) open()
  }, [linkToken, ready, open])

  const handleConnect = async () => {
    setConnecting(true)
    setError(null)
    setMessage(null)
    try {
      const token = await getPlaidLinkToken()
      setLinkToken(token)
    } catch (e) {
      setError((e as Error).message)
      setConnecting(false)
    }
  }

  const handleUnlink = async (itemId: string, name: string) => {
    if (!window.confirm(`Disconnect ${name}? This removes the link from Plaid and this app.`)) return
    setUnlinkingId(itemId)
    setError(null)
    setMessage(null)
    try {
      await unlinkPlaidItem(itemId)
      setMessage(`Disconnected ${name}`)
      await refreshStatus()
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setUnlinkingId(null)
    }
  }

  const readyToConnect =
    status?.configured &&
    status.encryption_configured &&
    !connecting &&
    !linkToken

  return (
    <div className="bg-white border border-paper-200 rounded-2xl p-4 space-y-3">
      <div className="flex items-start gap-3">
        <div className="w-10 h-10 rounded-xl bg-perk-100 border border-perk-200 flex items-center justify-center shrink-0">
          <Landmark size={18} className="text-perk-600" />
        </div>
        <div className="flex-1 min-w-0">
          <h3 className="text-sm font-semibold text-paper-800">Bank accounts</h3>
          <p className="text-xs text-paper-500 mt-0.5 leading-relaxed">
            Read-only via Plaid — spending sync comes next. Start in sandbox with fake banks.
          </p>
        </div>
      </div>

      {loading && <p className="text-xs text-paper-400">Checking bank connection…</p>}
      {error && <p className="text-xs text-red-500">{error}</p>}
      {message && <p className="text-xs text-friends-awning">{message}</p>}

      {!loading && status && (
        <>
          <div className="flex flex-wrap gap-2 text-[10px] font-semibold uppercase tracking-wide">
            <span
              className={`px-2 py-0.5 rounded-full ${
                status.configured ? 'bg-sage-100 text-sage-600' : 'bg-paper-100 text-paper-500'
              }`}
            >
              Plaid {status.configured ? 'configured' : 'not configured'}
            </span>
            <span
              className={`px-2 py-0.5 rounded-full ${
                status.encryption_configured
                  ? 'bg-sage-100 text-sage-600'
                  : 'bg-gold-100 text-gold-600'
              }`}
            >
              Encryption {status.encryption_configured ? 'on' : 'missing key'}
            </span>
            {status.configured && (
              <span className="px-2 py-0.5 rounded-full bg-paper-100 text-paper-500">
                {status.env}
              </span>
            )}
          </div>

          {!status.configured && (
            <p className="text-xs text-paper-600 leading-relaxed">
              Add <code className="text-[10px] bg-paper-50 px-1 rounded">PLAID_CLIENT_ID</code> and{' '}
              <code className="text-[10px] bg-paper-50 px-1 rounded">PLAID_SECRET</code> to{' '}
              <code className="text-[10px] bg-paper-50 px-1 rounded">backend/.env</code>, then restart
              the API.
            </p>
          )}

          {status.configured && !status.encryption_configured && (
            <p className="text-xs text-paper-600 leading-relaxed">
              Set <code className="text-[10px] bg-paper-50 px-1 rounded">PLAID_TOKEN_ENCRYPTION_KEY</code>{' '}
              in <code className="text-[10px] bg-paper-50 px-1 rounded">backend/.env</code> before linking
              a bank.
            </p>
          )}

          {status.items.length > 0 && (
            <ul className="space-y-2">
              {status.items.map((item) => (
                <li
                  key={item.item_id}
                  className="flex items-center justify-between gap-3 rounded-xl border border-paper-100 bg-paper-50 px-3 py-2.5"
                >
                  <div className="min-w-0">
                    <p className="text-sm font-medium text-paper-800 truncate">{item.institution_name}</p>
                    <p className="text-[10px] text-paper-400">Linked {formatLinkedAt(item.linked_at)}</p>
                  </div>
                  <button
                    type="button"
                    onClick={() => void handleUnlink(item.item_id, item.institution_name)}
                    disabled={unlinkingId === item.item_id}
                    className="shrink-0 flex items-center gap-1 text-xs font-medium text-paper-500 hover:text-red-600 disabled:opacity-50 min-h-[36px] px-2"
                  >
                    {unlinkingId === item.item_id ? (
                      <Loader2 size={14} className="animate-spin" />
                    ) : (
                      <Unlink size={14} />
                    )}
                    Disconnect
                  </button>
                </li>
              ))}
            </ul>
          )}

          <button
            type="button"
            onClick={() => void handleConnect()}
            disabled={!readyToConnect}
            className="w-full text-sm px-4 py-3 rounded-xl bg-perk-600 text-white disabled:opacity-50 min-h-[44px] touch-manipulation active:scale-[0.99] flex items-center justify-center gap-2"
          >
            {connecting || linkToken ? (
              <>
                <Loader2 size={16} className="animate-spin" />
                Opening Plaid…
              </>
            ) : (
              'Connect bank (sandbox)'
            )}
          </button>
        </>
      )}
    </div>
  )
}
