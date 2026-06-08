import { useCallback, useEffect, useRef, useState } from 'react'
import {
  getChatSessionMessages,
  getStoredActiveSessionId,
  isExplicitNewChat,
  listChatSessions,
  setStoredActiveSessionId,
  streamChat,
} from '@/lib/api'
import type {
  Attachment,
  BookItem,
  ChatSessionSummary,
  DigestItem,
  Intent,
  Message,
  SuggestItem,
} from '@/types'

function createMessageId(): string {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID()
  }
  return `msg-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`
}

function apiMessageToUi(row: Record<string, unknown>): Message {
  return {
    id: String(row.id ?? createMessageId()),
    role: row.role as Message['role'],
    content: String(row.content ?? ''),
    intent: row.intent as Intent | undefined,
    status: 'complete',
    digestItems: row.digestItems as DigestItem[] | undefined,
    suggestItems: row.suggestItems as SuggestItem[] | undefined,
    bookItems: row.bookItems as BookItem[] | undefined,
    obsidianPath: row.obsidianPath as string | undefined,
  }
}

export function useChat() {
  const [messages, setMessages] = useState<Message[]>([])
  const [sessions, setSessions] = useState<ChatSessionSummary[]>([])
  const [sessionId, setSessionId] = useState<string | null>(() => getStoredActiveSessionId())
  const [sending, setSending] = useState(false)
  const [loading, setLoading] = useState(true)
  const sessionIdRef = useRef<string | null>(sessionId)
  const messagesRef = useRef<Message[]>(messages)

  useEffect(() => {
    sessionIdRef.current = sessionId
    setStoredActiveSessionId(sessionId)
  }, [sessionId])

  useEffect(() => {
    messagesRef.current = messages
  }, [messages])

  const refreshSessions = useCallback(async () => {
    try {
      const rows = await listChatSessions()
      setSessions(rows)
      return rows
    } catch {
      return []
    }
  }, [])

  const loadSession = useCallback(async (id: string) => {
    setLoading(true)
    try {
      const data = await getChatSessionMessages(id)
      setSessionId(id)
      setMessages(data.messages.map(apiMessageToUi))
      await refreshSessions()
    } finally {
      setLoading(false)
    }
  }, [refreshSessions])

  const newChat = useCallback(() => {
    setSessionId(null)
    setMessages([])
    setStoredActiveSessionId(null)
    void refreshSessions()
  }, [refreshSessions])

  useEffect(() => {
    let cancelled = false

    async function bootstrap() {
      setLoading(true)
      try {
        const rows = await listChatSessions()
        if (cancelled) return
        setSessions(rows)

        const storedId = getStoredActiveSessionId()
        const explicitNew = isExplicitNewChat()
        const targetId =
          storedId ??
          (!explicitNew && rows.length > 0 ? (rows[0]?.id ?? null) : null)

        if (targetId) {
          const data = await getChatSessionMessages(targetId)
          if (cancelled) return
          setSessionId(targetId)
          setMessages(data.messages.map(apiMessageToUi))
        }
      } catch {
        /* offline or first run — start fresh */
      } finally {
        if (!cancelled) setLoading(false)
      }
    }

    void bootstrap()
    return () => {
      cancelled = true
    }
  }, [])

  const send = useCallback(async (text: string, attachments: Attachment[]) => {
    const userMsg: Message = {
      id: createMessageId(),
      role: 'user',
      content: text,
      attachments,
      status: 'complete',
    }
    const assistantMsg: Message = {
      id: createMessageId(),
      role: 'assistant',
      content: '',
      status: 'thinking',
    }
    setMessages((prev) => [...prev, userMsg, assistantMsg])
    setSending(true)

    const history = messagesRef.current
      .filter((m) => m.status === 'complete' && m.content.trim())
      .slice(-10)
      .map((m) => ({ role: m.role, content: m.content }))

    try {
      let activeSessionId = sessionIdRef.current

      for await (const evt of streamChat(text, attachments, history, activeSessionId)) {
        if (evt.event === 'session_id') {
          activeSessionId = evt.data
          sessionIdRef.current = evt.data
          setSessionId(evt.data)
          setStoredActiveSessionId(evt.data)
          void refreshSessions()
        }

        setMessages((prev) =>
          prev.map((m) => {
            if (m.id !== assistantMsg.id) return m
            switch (evt.event) {
              case 'status':
                return { ...m, status: 'thinking' }
              case 'message':
                return { ...m, content: m.content + evt.data, status: 'complete' }
              case 'intent':
                return { ...m, intent: evt.data as Intent }
              case 'digest_items':
                try {
                  const items = JSON.parse(evt.data) as DigestItem[]
                  return { ...m, digestItems: items }
                } catch {
                  return m
                }
              case 'suggest_items':
                try {
                  const items = JSON.parse(evt.data) as SuggestItem[]
                  return { ...m, suggestItems: items }
                } catch {
                  return m
                }
              case 'book_items':
                try {
                  const items = JSON.parse(evt.data) as BookItem[]
                  return { ...m, bookItems: items }
                } catch {
                  return m
                }
              case 'obsidian':
                return { ...m, obsidianPath: evt.data }
              case 'done':
                return { ...m, status: 'complete' }
              case 'error':
                return {
                  ...m,
                  status: 'error',
                  content: `⚠️ ${evt.data}`,
                }
              default:
                return m
            }
          }),
        )
      }

      void refreshSessions()
    } catch (err) {
      setMessages((prev) =>
        prev.map((m) =>
          m.id === assistantMsg.id
            ? { ...m, status: 'error', content: `⚠️ ${(err as Error).message}` }
            : m,
        ),
      )
    } finally {
      setSending(false)
    }
  }, [refreshSessions])

  return {
    messages,
    sending,
    loading,
    send,
    sessionId,
    sessions,
    loadSession,
    newChat,
    refreshSessions,
  }
}
