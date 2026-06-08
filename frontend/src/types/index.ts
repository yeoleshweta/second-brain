export type Intent = 'knowledge' | 'health' | 'finance' | 'calendar' | 'general'

export type AppView = 'chat' | 'reading' | 'agenda' | 'finance' | 'settings'

export interface DigestItem {
  title: string
  url: string
  summary: string
  source: string
  date: string
  kind: 'url' | 'paper' | 'note' | 'ebook' | 'audiobook'
  tag?: string
}

export interface SuggestItem extends DigestItem {
  id: string
  est_minutes: number
  in_list: boolean
  list_item_id?: number | null
  /** Direct PDF URL for inline preview (arXiv, etc.) */
  pdf_preview_url?: string
}

export interface BookItem {
  id: string
  gutenberg_id: number | null
  title: string
  authors: string
  summary: string
  url: string
  source: string
  kind: 'ebook' | 'audiobook'
  downloadable: boolean
  in_list: boolean
  /** Ocean of PDF search page vs direct /books/ URL */
  is_search?: boolean
}

export interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  intent?: Intent
  obsidianPath?: string
  attachments?: Attachment[]
  status?: 'thinking' | 'complete' | 'error'
  digestItems?: DigestItem[]
  suggestItems?: SuggestItem[]
  bookItems?: BookItem[]
}

export interface Attachment {
  fileId: string
  name: string
  mediaType: string
  size: number
}

export interface ChatStreamEvent {
  event:
    | 'status'
    | 'message'
    | 'intent'
    | 'obsidian'
    | 'done'
    | 'error'
    | 'digest_items'
    | 'suggest_items'
    | 'book_items'
    | 'session_id'
  data: string
}

export interface ChatSessionSummary {
  id: string
  title: string
  created_at: string
  updated_at: string
  message_count: number
}
