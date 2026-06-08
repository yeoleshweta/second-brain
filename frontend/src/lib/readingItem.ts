import type { ReadingItem } from '@/lib/api'

/** True when the item has in-app readable content (PDF, note, ebook). */
export function opensInAppReader(item: ReadingItem): boolean {
  if (item.content_format === 'pdf') return true
  if (item.kind === 'note' && item.has_content) return true
  if (item.kind === 'ebook' && item.has_content) return true
  return false
}
