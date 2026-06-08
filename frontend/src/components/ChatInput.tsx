import { useRef, useState } from 'react'
import { Send, X, Paperclip } from 'lucide-react'
import type { Attachment } from '@/types'
import { uploadFile } from '@/lib/api'

interface Props {
  onSend: (text: string, attachments: Attachment[]) => void
  disabled?: boolean
}

export function ChatInput({ onSend, disabled }: Props) {
  const [text, setText] = useState('')
  const [attachments, setAttachments] = useState<Attachment[]>([])
  const [uploading, setUploading] = useState(false)
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const fileRef = useRef<HTMLInputElement>(null)

  const canSend = (text.trim().length > 0 || attachments.length > 0) && !disabled && !uploading

  function autoResize() {
    const el = textareaRef.current
    if (!el) return
    el.style.height = 'auto'
    el.style.height = Math.min(el.scrollHeight, 120) + 'px'
  }

  function handleSubmit() {
    if (!canSend) return
    onSend(text.trim(), attachments)
    setText('')
    setAttachments([])
    requestAnimationFrame(() => {
      const el = textareaRef.current
      if (el) {
        el.style.height = 'auto'
      }
    })
  }

  function handleKeyDown(e: React.KeyboardEvent) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSubmit()
    }
  }

  async function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const files = Array.from(e.target.files ?? [])
    if (files.length === 0) return
    setUploading(true)
    try {
      for (const file of files) {
        const att = await uploadFile(file)
        setAttachments((prev) => [...prev, att])
      }
    } catch {
      alert('Upload failed — check your connection and try again.')
    } finally {
      setUploading(false)
      if (fileRef.current) fileRef.current.value = ''
    }
  }

  return (
    <div className="bg-white rounded-2xl border-2 border-friends-frame/70 shadow-card-lg overflow-hidden">
      {attachments.length > 0 && (
        <div className="flex flex-wrap gap-2 px-3 pt-3">
          {attachments.map((a) => (
            <div
              key={a.fileId}
              className="flex items-center gap-2 bg-paper-100 border border-paper-200 rounded-xl px-3 py-2 text-sm text-paper-600"
            >
              <span className="max-w-[140px] truncate">{a.name}</span>
              <button
                type="button"
                onClick={() => setAttachments((prev) => prev.filter((x) => x.fileId !== a.fileId))}
                className="touch-target flex items-center justify-center text-paper-400 active:text-rust-400 -mr-1"
                aria-label="Remove attachment"
              >
                <X size={16} />
              </button>
            </div>
          ))}
        </div>
      )}

      <div className="flex items-end gap-1.5 px-2 py-2 sm:px-3 sm:py-2.5">
        <button
          type="button"
          onClick={() => fileRef.current?.click()}
          disabled={uploading || disabled}
          className="touch-target shrink-0 flex items-center justify-center rounded-xl text-paper-500 active:bg-paper-100 active:text-friends-purple transition self-end"
          aria-label="Attach file"
        >
          <Paperclip size={22} />
        </button>
        <input
          ref={fileRef}
          type="file"
          multiple
          className="hidden"
          onChange={handleFileChange}
        />

        <textarea
          ref={textareaRef}
          rows={1}
          value={text}
          placeholder={disabled ? 'Ross is thinking…' : 'Message at centralperk…'}
          disabled={disabled}
          enterKeyHint="send"
          autoComplete="off"
          autoCorrect="on"
          className="input-ios flex-1 resize-none bg-transparent text-base text-paper-800 placeholder:text-paper-400 outline-none leading-relaxed py-2.5 min-h-[44px] max-h-[120px]"
          onChange={(e) => {
            setText(e.target.value)
            autoResize()
          }}
          onKeyDown={handleKeyDown}
        />

        <button
          type="button"
          onClick={handleSubmit}
          disabled={!canSend}
          aria-label="Send message"
          className={`touch-target shrink-0 rounded-xl flex items-center justify-center transition self-end active:scale-95 ${
            canSend
              ? 'bg-friends-sofa text-white shadow-card active:bg-friends-sofa-dark'
              : 'bg-paper-100 text-paper-300 cursor-not-allowed'
          }`}
        >
          {uploading ? (
            <span className="w-5 h-5 border-2 border-white/40 border-t-white rounded-full animate-spin" />
          ) : (
            <Send size={20} className={canSend ? 'text-white' : 'text-paper-300'} />
          )}
        </button>
      </div>
    </div>
  )
}
