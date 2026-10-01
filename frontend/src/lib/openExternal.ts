/**
 * Open a URL in the system browser or native app handler.
 *
 * Custom URL schemes (itms-books://, mailto:, etc.) must be opened with
 * window.location.href in iOS PWA standalone mode — target="_blank" silently
 * fails for non-http(s) schemes when running as a home-screen app.
 */
export function openExternalUrl(url: string): void {
  const trimmed = url.trim()
  if (!trimmed) return

  try {
    const parsed = new URL(trimmed)
    const isCustomScheme = !['http:', 'https:'].includes(parsed.protocol)

    if (isCustomScheme) {
      // For custom schemes (itms-books://, books://, etc.) use direct navigation
      // so iOS PWA standalone mode hands off to the correct native app.
      window.location.href = trimmed
      return
    }
  } catch {
    // Not a valid URL — fall through to <a> click
  }

  // For http(s) URLs open in Safari / system browser without leaving the PWA.
  const link = document.createElement('a')
  link.href = trimmed
  link.target = '_blank'
  link.rel = 'noopener noreferrer'
  link.style.display = 'none'
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
}

export function isExternalUrl(href: string): boolean {
  try {
    const url = new URL(href, window.location.origin)
    return url.origin !== window.location.origin
  } catch {
    return false
  }
}
