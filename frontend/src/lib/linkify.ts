const URL_RE = /https?:\/\/[^\s<]+/g

function trimUrl(url: string): { href: string; trail: string } {
  const href = url.replace(/[.,);:\]]+$/, '')
  return { href, trail: url.slice(href.length) }
}

/** Turn bare URLs into markdown links, leaving code spans and existing links alone. */
export function linkifyMarkdown(text: string): string {
  return text
    .split(/(`[^`]*`)/g)
    .map((part, index) => (index % 2 === 1 ? part : linkifyPlain(part)))
    .join('')
}

function linkifyPlain(segment: string): string {
  return segment.replace(/(^|[^(\[])(https?:\/\/[^\s<]+)/g, (_full, prefix: string, url: string) => {
    const { href, trail } = trimUrl(url)
    return `${prefix}[${href}](${href})${trail}`
  })
}

export function splitLinks(text: string): Array<{ kind: 'text' | 'link'; value: string }> {
  const parts: Array<{ kind: 'text' | 'link'; value: string }> = []
  let last = 0
  for (const match of text.matchAll(URL_RE)) {
    const start = match.index ?? 0
    if (start > last) parts.push({ kind: 'text', value: text.slice(last, start) })
    const { href, trail } = trimUrl(match[0])
    parts.push({ kind: 'link', value: href })
    if (trail) parts.push({ kind: 'text', value: trail })
    last = start + match[0].length
  }
  if (last < text.length) parts.push({ kind: 'text', value: text.slice(last) })
  return parts
}
