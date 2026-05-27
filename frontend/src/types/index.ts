export type Intent = 'knowledge' | 'health' | 'finance' | 'calendar' | 'general'

export interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  intent?: Intent
  obsidianPath?: string
  attachments?: Attachment[]
  status?: 'thinking' | 'complete' | 'error'
}

export interface Attachment {
  fileId: string
  name: string
  mediaType: string
  size: number
}

export interface ChatStreamEvent {
  event: 'status' | 'message' | 'intent' | 'obsidian' | 'done' | 'error'
  data: string
}
