export type Intent = 'knowledge' | 'health' | 'finance' | 'calendar' | 'general'

export interface DigestItem {
  title: string
  url: string
  summary: string
  source: string
  date: string
  kind: 'url' | 'paper' | 'note'
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
}

export interface Attachment {
  fileId: string
  name: string
  mediaType: string
  size: number
}

export interface ChatStreamEvent {
  event: 'status' | 'message' | 'intent' | 'obsidian' | 'done' | 'error' | 'digest_items'
  data: string
}
