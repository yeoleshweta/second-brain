import { useRef, useState } from 'react'
import { Send, X, Paperclip, Mic, Camera, PhoneOff } from 'lucide-react'
import type { Attachment } from '@/types'
import { uploadFile } from '@/lib/api'
import { micSupported, transcribeUpload } from '@/lib/voice'
import type { VoicePhase } from '@/lib/voice'

interface VoiceControls {
  active: boolean
  phase: VoicePhase
  onToggle: () => void
}

interface Props {
  onSend: (text: string, attachments: Attachment[]) => void
  disabled?: boolean
  voice?: VoiceControls
}

export function ChatInput({ onSend, disabled, voice }: Props) {
  const [text, setText] = useState('')
  const [attachments, setAttachments] = useState<Attachment[]>([])
  const [uploading, setUploading] = useState(false)
  const [recordError, setRecordError] = useState<string | null>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const fileRef = useRef<HTMLInputElement>(null)
  const cameraRef = useRef<HTMLInputElement>(null)

  const canSend =
    (text.trim().length > 0 || attachments.length > 0) &&
    !disabled &&
    !uploading &&
    !voice?.active

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
      if (el) el.style.height = 'auto'
    })
  }

  function handleKeyDown(e: React.KeyboardEvent) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSubmit()
    }
  }

  async function ingestFiles(files: File[]) {
    if (files.length === 0) return
    setUploading(true)
    setRecordError(null)
    try {
      for (const file of files) {
        const att = await uploadFile(file)
        setAttachments((prev) => [...prev, att])
        if (file.type.startsWith('audio/') || file.type.startsWith('video/')) {
          try {
            const spoken = await transcribeUpload(att.fileId)
            if (spoken) {
              setText((prev) => (prev.trim() ? `${prev.trim()} ${spoken}` : spoken))
              requestAnimationFrame(autoResize)
            }
          } catch (err) {
            setRecordError(
              err instanceof Error
                ? err.message
                : 'Could not transcribe that audio. Send it anyway — the backend will retry.',
            )
          }
        }
      }
    } catch {
      setRecordError('Upload failed — check your connection and try again.')
    } finally {
      setUploading(false)
      if (fileRef.current) fileRef.current.value = ''
      if (cameraRef.current) cameraRef.current.value = ''
    }
  }

  async function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    await ingestFiles(Array.from(e.target.files ?? []))
  }

  async function handlePaste(e: React.ClipboardEvent) {
    const files = Array.from(e.clipboardData.items)
      .filter((item) => item.kind === 'file')
      .map((item) => item.getAsFile())
      .filter((f): f is File => !!f)
    if (files.length === 0) return
    e.preventDefault()
    await ingestFiles(files)
  }

  function handleMic() {
    setRecordError(null)
    if (voice) {
      if (!micSupported() && !voice.active) {
        setRecordError(
          'Live mic needs HTTPS (or localhost). On iPhone over Tailscale HTTP, attach a Voice Memo instead.',
        )
        fileRef.current?.click()
      }
      voice.onToggle()
      return
    }
    fileRef.current?.click()
  }

  return (
    <div
      className="bg-white rounded-2xl border border-paper-200 shadow-card-lg overflow-hidden"
      onPaste={handlePaste}
      onDragOver={(e) => e.preventDefault()}
      onDrop={(e) => {
        e.preventDefault()
        void ingestFiles(Array.from(e.dataTransfer.files))
      }}
    >
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

      {recordError && (
        <p className="px-3 pt-2 text-[11px] text-paper-500 leading-snug">{recordError}</p>
      )}

      <div className="flex items-end gap-1 px-2 py-2 sm:px-3 sm:py-2.5">
        <button
          type="button"
          onClick={() => cameraRef.current?.click()}
          disabled={uploading || disabled || voice?.active}
          className="touch-target shrink-0 flex items-center justify-center rounded-xl text-paper-500 active:bg-paper-100 active:text-friends-purple transition self-end"
          aria-label="Take photo"
        >
          <Camera size={22} />
        </button>
        <button
          type="button"
          onClick={() => fileRef.current?.click()}
          disabled={uploading || disabled || voice?.active}
          className="touch-target shrink-0 flex items-center justify-center rounded-xl text-paper-500 active:bg-paper-100 active:text-friends-purple transition self-end"
          aria-label="Attach file"
        >
          <Paperclip size={22} />
        </button>
        <input
          ref={cameraRef}
          type="file"
          accept="image/*"
          capture="environment"
          className="hidden"
          onChange={handleFileChange}
        />
        <input
          ref={fileRef}
          type="file"
          multiple
          accept="image/*,audio/*,video/*,.pdf,.txt,.md,.doc,.docx"
          className="hidden"
          onChange={handleFileChange}
        />

        <textarea
          ref={textareaRef}
          rows={1}
          value={text}
          placeholder={
            voice?.active
              ? 'Talk mode on — speak, or type here to cancel'
              : disabled
                ? 'Thinking…'
                : 'Talk, or “remember this…” / “write this down…”'
          }
          disabled={disabled || voice?.active}
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
          onClick={handleMic}
          disabled={uploading || (disabled && !voice?.active)}
          className={`touch-target shrink-0 flex items-center justify-center rounded-xl transition self-end ${
            voice?.active
              ? 'bg-rust-400 text-white'
              : 'text-paper-500 active:bg-paper-100 active:text-friends-purple'
          }`}
          aria-label={voice?.active ? 'Hang up' : 'Talk'}
        >
          {voice?.active ? <PhoneOff size={18} /> : <Mic size={22} />}
        </button>

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
      {!voice?.active && !disabled && (
        <p className="px-3 pb-2 text-[11px] text-paper-400">
          Capture: remember this / write this down
        </p>
      )}
    </div>
  )
}
