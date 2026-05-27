import { useCallback, useState } from 'react'
import { streamChat } from '@/lib/api'
import type { Message, Attachment, Intent } from '@/types'

export function useChat() {
  const [messages, setMessages] = useState<Message[]>([])
  const [sending, setSending] = useState(false)

  const send = useCallback(async (text: string, attachments: Attachment[]) => {
    const userMsg: Message = {
      id: crypto.randomUUID(),
      role: 'user',
      content: text,
      attachments,
      status: 'complete',
    }
    const assistantMsg: Message = {
      id: crypto.randomUUID(),
      role: 'assistant',
      content: '',
      status: 'thinking',
    }
    setMessages((prev) => [...prev, userMsg, assistantMsg])
    setSending(true)

    try {
      for await (const evt of streamChat(text, attachments)) {
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
  }, [])

  return { messages, sending, send }
}
