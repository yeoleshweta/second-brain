import { useEffect, useMemo, useState } from 'react'
import { getRossSettings, getTodayUsage, patchRossSettings, type RossSettings } from '@/lib/api'
import { PlaidConnectSection } from '@/components/PlaidConnect'

function asBool(v: string | undefined): boolean {
  return (v || '').toLowerCase() === 'true'
}

export function SettingsView() {
  const [settings, setSettings] = useState<RossSettings | null>(null)
  const [usage, setUsage] = useState<{ estimated_cost_usd: number; total_tokens: number } | null>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    Promise.all([getRossSettings(), getTodayUsage()])
      .then(([s, u]) => {
        setSettings(s)
        setUsage({ estimated_cost_usd: u.estimated_cost_usd, total_tokens: u.total_tokens })
      })
      .catch((e) => setError((e as Error).message))
      .finally(() => setLoading(false))
  }, [])

  const skillList = useMemo(
    () => (settings?.active_skills || '').split(',').map((s) => s.trim()).filter(Boolean),
    [settings],
  )

  const savePatch = async (patch: Parameters<typeof patchRossSettings>[0]) => {
    setSaving(true)
    setError(null)
    try {
      const next = await patchRossSettings(patch)
      setSettings(next)
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setSaving(false)
    }
  }

  const toggles: { key: keyof RossSettings; label: string }[] = [
    { key: 'nudge_morning_brief', label: 'Morning brief' },
    { key: 'nudge_mid_day_reading', label: 'Mid-day reading' },
    { key: 'nudge_evening_reading', label: 'Evening reading' },
    { key: 'nudge_evening_practice', label: 'Evening practice' },
    { key: 'nudge_weekly_review', label: 'Weekly review' },
    { key: 'nudge_discovery', label: 'Discovery' },
  ]

  if (loading) return <div className="p-5 text-sm text-paper-500">Loading settings...</div>
  if (!settings) return <div className="p-5 text-sm text-red-500">{error || 'No settings found.'}</div>

  return (
    <div className="h-full overflow-y-auto mobile-scroll">
      <div className="max-w-2xl mx-auto px-4 py-4 md:py-5 space-y-4">
        <h2 className="font-serif text-xl font-bold text-paper-800 hidden md:block">Settings</h2>
        {error && <p className="text-xs text-red-500">{error}</p>}

        <PlaidConnectSection />

        <div className="bg-white border border-paper-200 rounded-2xl p-4 space-y-3">
          <h3 className="text-sm font-semibold text-paper-700">Ross — reading & practice</h3>
          <label className="block text-sm text-paper-700">
            Daily reading goal (minutes)
            <input
              type="number"
              className="input-ios mt-1 w-full border border-paper-200 rounded-xl px-3 py-3 min-h-[44px]"
              value={settings.daily_reading_minutes_goal || '15'}
              onChange={(e) => setSettings({ ...settings, daily_reading_minutes_goal: e.target.value })}
              onBlur={() => savePatch({ daily_reading_minutes_goal: Number(settings.daily_reading_minutes_goal || 0) })}
            />
          </label>
          <label className="block text-sm text-paper-700">
            Daily practice goal (minutes)
            <input
              type="number"
              className="input-ios mt-1 w-full border border-paper-200 rounded-xl px-3 py-3 min-h-[44px]"
              value={settings.daily_practice_minutes_goal || '60'}
              onChange={(e) => setSettings({ ...settings, daily_practice_minutes_goal: e.target.value })}
              onBlur={() => savePatch({ daily_practice_minutes_goal: Number(settings.daily_practice_minutes_goal || 0) })}
            />
          </label>
          <div className="text-sm text-paper-700">
            Active skills
            <div className="mt-2 flex flex-wrap gap-2">
              {skillList.map((s) => (
                <span key={s} className="px-2 py-1 text-xs rounded-full bg-paper-100 border border-paper-200">
                  {s}
                </span>
              ))}
            </div>
            <button
              className="mt-3 text-sm px-4 py-3 rounded-xl bg-paper-800 text-white disabled:opacity-50 min-h-[44px] touch-manipulation active:scale-[0.99]"
              disabled={saving}
              onClick={() => {
                const next = prompt('Add skill')
                if (!next) return
                const updated = Array.from(new Set([...skillList, next.toLowerCase().trim()]))
                savePatch({ active_skills: updated })
              }}
            >
              Add skill
            </button>
          </div>
        </div>

        <div className="bg-white border border-paper-200 rounded-2xl p-4 space-y-3">
          <h3 className="text-sm font-semibold text-paper-700">Quiet hours</h3>
          <div className="grid grid-cols-2 gap-3">
            <input
              type="time"
              className="input-ios border border-paper-200 rounded-xl px-3 py-3 min-h-[44px] w-full"
              value={settings.quiet_hours_start || '22:00'}
              onChange={(e) => setSettings({ ...settings, quiet_hours_start: e.target.value })}
              onBlur={() => savePatch({ quiet_hours_start: settings.quiet_hours_start })}
            />
            <input
              type="time"
              className="input-ios border border-paper-200 rounded-xl px-3 py-3 min-h-[44px] w-full"
              value={settings.quiet_hours_end || '06:00'}
              onChange={(e) => setSettings({ ...settings, quiet_hours_end: e.target.value })}
              onBlur={() => savePatch({ quiet_hours_end: settings.quiet_hours_end })}
            />
          </div>
        </div>

        <div className="bg-white border border-paper-200 rounded-2xl p-4 space-y-2">
          <h3 className="text-sm font-semibold text-paper-700">Nudge channels</h3>
          {toggles.map(({ key, label }) => (
            <label key={key} className="flex items-center justify-between text-sm text-paper-700 min-h-[48px] py-1 touch-manipulation">
              <span>{label}</span>
              <input
                type="checkbox"
                className="w-5 h-5 accent-friends-purple"
                checked={asBool(settings[key])}
                onChange={(e) =>
                  savePatch({ [key]: e.target.checked } as Parameters<typeof patchRossSettings>[0])
                }
              />
            </label>
          ))}
        </div>

        <div className="bg-white border border-paper-200 rounded-2xl p-4">
          <h3 className="text-sm font-semibold text-paper-700">Usage today</h3>
          <p className="text-xs text-paper-500 mt-1">
            Estimated cost: ${usage?.estimated_cost_usd.toFixed(4) || '0.0000'} · {usage?.total_tokens || 0} tokens
          </p>
        </div>
      </div>
    </div>
  )
}
