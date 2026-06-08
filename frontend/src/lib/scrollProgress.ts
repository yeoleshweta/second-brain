/** Scroll position as 0–100 based on how far the user has scrolled. */
export function scrollToPercent(el: HTMLElement): number {
  const max = el.scrollHeight - el.clientHeight
  if (max <= 0) return 100
  return Math.round(Math.min(100, Math.max(0, (el.scrollTop / max) * 100)))
}

/** Debounce helper for persisting scroll progress. */
export function debounceByKey<T extends string | number>(
  timers: Map<T, ReturnType<typeof setTimeout>>,
  key: T,
  fn: () => void,
  ms: number,
): void {
  const existing = timers.get(key)
  if (existing) clearTimeout(existing)
  timers.set(key, setTimeout(fn, ms))
}
