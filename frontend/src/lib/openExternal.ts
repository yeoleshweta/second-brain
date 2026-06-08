/**
 * Open a URL in the system browser (Safari on iPhone).
 * Never navigates the Central Perk PWA webview to external sites.
 */
export function openExternalUrl(url: string): void {
  const trimmed = url.trim()
  if (!trimmed) return

  // Prefer a real <a target="_blank"> click — opens Safari / system browser on iOS PWA.
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
