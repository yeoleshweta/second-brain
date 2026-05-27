import { useRef, useState, type KeyboardEvent } from 'react'
import { Paperclip, Send, X } from 'lucide-react'
import { uploadFile } from '@/lib/api'
import type { Attachment } from '@/types'

interface Props {
  onSend: (message: string, attachments: Attachment[]) => void
  disabled?: boolean
}

export function ChatInput({ onSend, disabled }: Props) {
  const [text, setText] = useState('')
  const [attachments, setAttachments] = useState<Attachment[]>([])
  const [uploading, setUploading] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)

  function submit() {
    if (disabled || uploading) return
    if (!text.trim() && attachments.length === 0) return
    onSend(text.trim() || '(attachment)', attachments)
    setText('')
    setAttachments([])
  }

  function onKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      submit()
    }
  }

  async function onFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const files = e.target.files
    if (!files) return
    setUploading(true)
    try {
      const uploaded: Attachment[] = []
      for (const file of Array.from(files)) {
        const a = await uploadFile(file)
        uploaded.push(a)
      }
      setAttachments((prev) => [...prev, ...uploaded])
    } catch (err) {
      alert(`Upload failed: ${(err as Error).message}`)
    } finally {
      setUploading(false)
      if (fileInputRef.current) fileInputRef.current.value = ''
    }
  }

  function removeAttachment(fileId: string) {
    setAttachments((prev) => prev.filter((a) => a.fileId !== fileId))
  }

  return (
    <div className="border-t border-ink-700 bg-ink-800/50 backdrop-blur">
      {attachments.length > 0 && (
        <div className="px-4 pt-3 flex flex-wrap gap-2">
          {attachments.map((a) => (
            <div
              key={a.fileId}
              className="flex items-center gap-2 bg-ink-700 rounded-md px-2.5 py-1.5 text-sm"
            >
              <span className="text-ink-200">{a.name}</span>
              <button
                onClick={() => removeAttachment(a.fileId)}
                className="text-ink-400 hover:text-ink-100"
              >
                <X size={14} />
              </button>
            </div>
          ))}
        </div>
      )}

      <div className="p-4 flex items-end gap-2">
        <input
          ref={fileInputRef}
          type="file"
          className="hidden"
          accept="image/*,application/pdf"
          multiple
          onChange={onFileChange}
        />
        <button
          onClick={() => fileInputRef.current?.click()}
          disabled={disabled || uploading}
          className="p-2.5 rounded-lg bg-ink-700 hover:bg-ink-600 text-ink-200 disabled:opacity-50"
          title="Attach file"
        >
          <Paperclip size={18} />
        </button>

        <textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={onKeyDown}
          placeholder={
            uploading ? 'Uploading…' : 'Tell your brain anything (Shift+Enter for newline)'
          }
          rows={1}
          disabled={disabled || uploading}
          className="flex-1 resize-none bg-ink-900 border border-ink-700 rounded-lg px-3 py-2.5 text-ink-100 placeholder-ink-400 focus:outline-none focus:border-blue-500"
          style={{ maxHeight: '160px' }}
        />

        <button
          onClick={submit}
          disabled={disabled || uploading || (!text.trim() && attachments.length === 0)}
          className="p-2.5 rounded-lg bg-blue-600 hover:bg-blue-500 text-white disabled:opacity-40 disabled:cursor-not-allowed"
          title="Send"
        >
          <Send size={18} />
        </button>
      </div>
    </div>
  )
}
