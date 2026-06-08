import { useCallback, useEffect, useState } from 'react'
import { AlertCircle, RefreshCw, TrendingDown, CreditCard, Repeat2, DollarSign } from 'lucide-react'
import {
  getFinanceSummary,
  getFinanceTransactions,
  triggerFinanceSync,
  getPlaidStatus,
  type FinanceSummary,
  type Transaction,
} from '@/lib/api'
import { CharacterAvatarByAgentId } from '@/components/friends/CharacterAvatar'

type Period = 'week' | 'month' | 'last_month' | 'year'

const PERIODS: { id: Period; label: string }[] = [
  { id: 'week', label: 'This week' },
  { id: 'month', label: 'This month' },
  { id: 'last_month', label: 'Last month' },
  { id: 'year', label: 'This year' },
]

// Colour palette for categories — cycles through friendly colours
const CAT_COLORS = [
  'bg-perk-400',
  'bg-friends-purple',
  'bg-friends-coral',
  'bg-friends-teal',
  'bg-amber-400',
  'bg-sky-400',
  'bg-emerald-400',
  'bg-pink-400',
  'bg-indigo-400',
  'bg-orange-400',
]

function CategoryBar({
  categories,
  total,
}: {
  categories: FinanceSummary['categories']
  total: number
}) {
  if (!categories.length) return null
  return (
    <div className="space-y-2">
      {categories.slice(0, 8).map((cat, i) => {
        const pct = total > 0 ? (cat.total / total) * 100 : 0
        return (
          <div key={cat.category} className="flex items-center gap-3">
            <div className={`w-2.5 h-2.5 rounded-full shrink-0 ${CAT_COLORS[i % CAT_COLORS.length]}`} />
            <div className="flex-1 min-w-0">
              <div className="flex justify-between text-xs mb-0.5">
                <span className="truncate text-paper-700 font-medium">{cat.category}</span>
                <span className="text-paper-500 shrink-0 ml-2">${cat.total.toFixed(2)}</span>
              </div>
              <div className="h-1.5 bg-paper-100 rounded-full overflow-hidden">
                <div
                  className={`h-full rounded-full ${CAT_COLORS[i % CAT_COLORS.length]}`}
                  style={{ width: `${Math.min(pct, 100)}%` }}
                />
              </div>
            </div>
          </div>
        )
      })}
    </div>
  )
}

function TransactionRow({ tx }: { tx: Transaction }) {
  const isIncome = tx.amount < 0
  return (
    <div className="flex items-center gap-3 py-2.5 border-b border-paper-50 last:border-0">
      <div className="w-8 h-8 rounded-full bg-paper-100 flex items-center justify-center shrink-0">
        <CreditCard size={14} className="text-paper-400" />
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium text-paper-800 truncate">{tx.merchant || 'Unknown'}</p>
        <p className="text-xs text-paper-400">{tx.date} · {tx.category || 'Uncategorized'}</p>
      </div>
      <div className="text-right shrink-0">
        <p className={`text-sm font-semibold ${isIncome ? 'text-emerald-600' : 'text-paper-800'}`}>
          {isIncome ? '+' : '-'}${Math.abs(tx.amount).toFixed(2)}
        </p>
        {tx.pending && (
          <p className="text-xs text-amber-500">Pending</p>
        )}
      </div>
    </div>
  )
}

function EmptyState({ syncing, onSync }: { syncing: boolean; onSync: () => void }) {
  return (
    <div className="flex flex-col items-center justify-center py-16 px-6 text-center gap-4">
      <div className="w-16 h-16 rounded-full bg-perk-50 border border-perk-100 flex items-center justify-center">
        <DollarSign size={28} className="text-perk-400" />
      </div>
      <div>
        <p className="font-semibold text-paper-700">No transactions yet</p>
        <p className="text-sm text-paper-400 mt-1">
          Connect your bank in Settings, then sync to load your transactions.
        </p>
      </div>
      <button
        onClick={onSync}
        disabled={syncing}
        className="flex items-center gap-2 px-5 py-2.5 rounded-xl bg-perk-500 text-white text-sm font-medium hover:bg-perk-600 disabled:opacity-50 transition-colors"
      >
        <RefreshCw size={14} className={syncing ? 'animate-spin' : ''} />
        {syncing ? 'Syncing…' : 'Sync now'}
      </button>
    </div>
  )
}

export default function FinanceDashboard() {
  const [period, setPeriod] = useState<Period>('month')
  const [summary, setSummary] = useState<FinanceSummary | null>(null)
  const [transactions, setTransactions] = useState<Transaction[]>([])
  const [plaidLinked, setPlaidLinked] = useState(false)
  const [loading, setLoading] = useState(true)
  const [syncing, setSyncing] = useState(false)
  const [syncMsg, setSyncMsg] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [activeTab, setActiveTab] = useState<'overview' | 'transactions' | 'subscriptions'>('overview')

  const loadData = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const [sumData, txData, plaidData] = await Promise.all([
        getFinanceSummary(period).catch(() => null),
        getFinanceTransactions(period, 50).catch(() => null),
        getPlaidStatus().catch(() => null),
      ])
      setSummary(sumData)
      setTransactions(txData?.transactions ?? [])
      setPlaidLinked(plaidData?.linked ?? false)
    } catch (e) {
      setError('Failed to load finance data')
    } finally {
      setLoading(false)
    }
  }, [period])

  useEffect(() => { loadData() }, [loadData])

  const handleSync = async () => {
    setSyncing(true)
    setSyncMsg(null)
    try {
      const result = await triggerFinanceSync()
      const totals = result.results.reduce(
        (acc, r) => ({
          added: acc.added + (r.added ?? 0),
          inst: [...acc.inst, r.institution ?? ''],
        }),
        { added: 0, inst: [] as string[] },
      )
      setSyncMsg(`Synced ${totals.inst.filter(Boolean).join(', ')} — ${totals.added} new transactions`)
      await loadData()
    } catch (e) {
      setSyncMsg('Sync failed — check Plaid settings')
    } finally {
      setSyncing(false)
      setTimeout(() => setSyncMsg(null), 6000)
    }
  }

  const hasData = (summary?.total ?? 0) > 0 || transactions.length > 0

  return (
    <div className="flex flex-col h-full overflow-hidden bg-friends-cream/30">
      {/* Header */}
      <div className="flex items-center gap-3 px-4 pt-4 pb-2 shrink-0">
        <CharacterAvatarByAgentId agentId="finance" size="sm" />
        <div className="flex-1 min-w-0">
          <h2 className="text-base font-bold text-paper-800 leading-tight">Finance</h2>
          <p className="text-xs text-paper-400">Powered by Plaid · read-only</p>
        </div>
        <button
          onClick={handleSync}
          disabled={syncing || !plaidLinked}
          title={plaidLinked ? 'Sync transactions' : 'Connect a bank in Settings first'}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl border border-paper-200 text-xs text-paper-600 hover:bg-paper-50 disabled:opacity-40 transition-colors"
        >
          <RefreshCw size={12} className={syncing ? 'animate-spin' : ''} />
          {syncing ? 'Syncing…' : 'Sync'}
        </button>
      </div>

      {/* Sync message */}
      {syncMsg && (
        <div className="mx-4 mb-2 px-3 py-2 rounded-xl bg-emerald-50 border border-emerald-200 text-xs text-emerald-700">
          {syncMsg}
        </div>
      )}

      {/* Period selector */}
      <div className="flex gap-1 px-4 mb-3 shrink-0 overflow-x-auto no-scrollbar">
        {PERIODS.map((p) => (
          <button
            key={p.id}
            onClick={() => setPeriod(p.id)}
            className={`shrink-0 px-3 py-1.5 rounded-full text-xs font-medium transition-colors ${
              period === p.id
                ? 'bg-perk-500 text-white shadow-sm'
                : 'bg-white border border-paper-200 text-paper-600 active:border-perk-300'
            }`}
          >
            {p.label}
          </button>
        ))}
      </div>

      {/* Tabs */}
      <div className="flex gap-0 px-4 mb-3 shrink-0 border-b border-paper-100">
        {(['overview', 'transactions', 'subscriptions'] as const).map((tab) => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className={`px-4 py-2 text-xs font-medium border-b-2 -mb-px transition-colors ${
              activeTab === tab
                ? 'border-perk-500 text-perk-600'
                : 'border-transparent text-paper-500 hover:text-paper-700'
            }`}
          >
            {tab.charAt(0).toUpperCase() + tab.slice(1)}
          </button>
        ))}
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto px-4 pb-6">
        {error && (
          <div className="flex items-center gap-2 p-3 rounded-xl bg-red-50 border border-red-100 text-sm text-red-600 mb-4">
            <AlertCircle size={14} className="shrink-0" />
            {error}
          </div>
        )}

        {loading ? (
          <div className="flex items-center justify-center py-16 text-paper-400 text-sm">
            Loading…
          </div>
        ) : !hasData ? (
          <EmptyState syncing={syncing} onSync={handleSync} />
        ) : (
          <>
            {/* Overview tab */}
            {activeTab === 'overview' && summary && (
              <div className="space-y-4">
                {/* Total spend card */}
                <div className="bg-white rounded-2xl border border-paper-100 shadow-card p-4 flex items-center gap-4">
                  <div className="w-12 h-12 rounded-xl bg-perk-50 border border-perk-100 flex items-center justify-center shrink-0">
                    <TrendingDown size={20} className="text-perk-500" />
                  </div>
                  <div>
                    <p className="text-xs text-paper-400 uppercase tracking-wide font-medium">
                      Total spent · {PERIODS.find((p) => p.id === period)?.label}
                    </p>
                    <p className="text-2xl font-bold text-paper-800">
                      ${summary.total.toLocaleString('en-US', { minimumFractionDigits: 2 })}
                    </p>
                  </div>
                </div>

                {/* Category breakdown */}
                {summary.categories.length > 0 && (
                  <div className="bg-white rounded-2xl border border-paper-100 shadow-card p-4">
                    <p className="text-xs font-semibold text-paper-500 uppercase tracking-wide mb-3">
                      Spending by category
                    </p>
                    <CategoryBar categories={summary.categories} total={summary.total} />
                  </div>
                )}

                {/* Subscriptions preview */}
                {summary.subscriptions.length > 0 && (
                  <div className="bg-white rounded-2xl border border-paper-100 shadow-card p-4">
                    <div className="flex items-center gap-2 mb-3">
                      <Repeat2 size={14} className="text-friends-purple" />
                      <p className="text-xs font-semibold text-paper-500 uppercase tracking-wide">
                        Subscriptions (~${summary.subscriptions.reduce((s, x) => s + x.avg_amount, 0).toFixed(2)}/mo)
                      </p>
                    </div>
                    <div className="space-y-2">
                      {summary.subscriptions.slice(0, 5).map((sub) => (
                        <div key={sub.merchant} className="flex items-center justify-between text-sm">
                          <span className="text-paper-700">{sub.merchant}</span>
                          <span className="text-paper-500 font-medium">${sub.avg_amount.toFixed(2)}/mo</span>
                        </div>
                      ))}
                    </div>
                    {summary.subscriptions.length > 5 && (
                      <button
                        onClick={() => setActiveTab('subscriptions')}
                        className="mt-2 text-xs text-perk-500 hover:underline"
                      >
                        +{summary.subscriptions.length - 5} more
                      </button>
                    )}
                  </div>
                )}
              </div>
            )}

            {/* Transactions tab */}
            {activeTab === 'transactions' && (
              <div className="bg-white rounded-2xl border border-paper-100 shadow-card p-4">
                {transactions.length === 0 ? (
                  <p className="text-sm text-paper-400 text-center py-6">No transactions for this period.</p>
                ) : (
                  <div>
                    <p className="text-xs text-paper-400 mb-2">{transactions.length} transactions</p>
                    {transactions.map((tx) => (
                      <TransactionRow key={tx.plaid_transaction_id} tx={tx} />
                    ))}
                  </div>
                )}
              </div>
            )}

            {/* Subscriptions tab */}
            {activeTab === 'subscriptions' && summary && (
              <div className="space-y-3">
                {summary.subscriptions.length === 0 ? (
                  <p className="text-sm text-paper-400 text-center py-6">
                    No subscriptions detected yet. Sync 2+ months of data for best results.
                  </p>
                ) : (
                  summary.subscriptions.map((sub) => (
                    <div
                      key={sub.merchant}
                      className="bg-white rounded-2xl border border-paper-100 shadow-card p-4 flex items-center gap-3"
                    >
                      <div className="w-10 h-10 rounded-xl bg-friends-purple/10 border border-friends-purple/20 flex items-center justify-center shrink-0">
                        <Repeat2 size={16} className="text-friends-purple" />
                      </div>
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-semibold text-paper-800">{sub.merchant}</p>
                        <p className="text-xs text-paper-400">
                          {sub.occurrences}× in 90 days · last {sub.last_charged ?? '—'}
                        </p>
                      </div>
                      <p className="text-sm font-bold text-paper-700 shrink-0">
                        ${sub.avg_amount.toFixed(2)}<span className="text-xs font-normal text-paper-400">/mo</span>
                      </p>
                    </div>
                  ))
                )}
              </div>
            )}
          </>
        )}
      </div>
    </div>
  )
}
