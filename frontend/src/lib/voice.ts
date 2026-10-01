import type { Intent } from '@/types'
import { fetchSpeechAudio, transcribeUpload, uploadFile } from '@/lib/api'

export { transcribeUpload }

const VOICE_KEY = 'centralperk_voice_replies'
let currentAudio: HTMLAudioElement | null = null
let currentUrl: string | null = null
let speakWaiters: Array<() => void> = []

export type VoicePhase =
  | 'idle'
  | 'connecting'
  | 'listening'
  | 'transcribing'
  | 'waiting'
  | 'speaking'
  | 'blocked'

export function isVoiceRepliesEnabled(): boolean {
  try {
    return localStorage.getItem(VOICE_KEY) === '1'
  } catch {
    return false
  }
}

export function setVoiceRepliesEnabled(on: boolean): void {
  localStorage.setItem(VOICE_KEY, on ? '1' : '0')
  if (!on) stopSpeaking()
}

function finishSpeakWaiters(): void {
  const waiters = speakWaiters
  speakWaiters = []
  for (const done of waiters) done()
}

export function stopSpeaking(): void {
  if (currentAudio) {
    currentAudio.onended = null
    currentAudio.onerror = null
    currentAudio.pause()
    currentAudio.src = ''
    currentAudio = null
  }
  if (currentUrl) {
    URL.revokeObjectURL(currentUrl)
    currentUrl = null
  }
  finishSpeakWaiters()
}

/** iOS only unlocks audio playback after a user gesture. Call from the Talk tap. */
export async function unlockAudioPlayback(): Promise<void> {
  const beep = new Audio(
    'data:audio/wav;base64,UklGRigAAABXQVZFZm10IBIAAAABAAEARKwAAIhYAQACABAAAABkYXRhAgAAAAEA',
  )
  beep.volume = 0.01
  try {
    await beep.play()
  } catch {
    /* getUserMedia often unlocks playback on the same gesture */
  }
  beep.pause()
}

export async function speakReply(text: string, intent?: Intent): Promise<void> {
  stopSpeaking()
  const blob = await fetchSpeechAudio(text, intent)
  currentUrl = URL.createObjectURL(blob)
  currentAudio = new Audio(currentUrl)
  await new Promise<void>((resolve, reject) => {
    if (!currentAudio) {
      resolve()
      return
    }
    speakWaiters.push(resolve)
    currentAudio.onended = () => {
      stopSpeaking()
    }
    currentAudio.onerror = () => {
      stopSpeaking()
    }
    void currentAudio.play().catch((err: unknown) => {
      stopSpeaking()
      reject(err)
    })
  })
}

export function micSupported(): boolean {
  return (
    typeof window !== 'undefined' &&
    window.isSecureContext &&
    !!navigator.mediaDevices?.getUserMedia &&
    typeof MediaRecorder !== 'undefined'
  )
}

export function micBlockReason(): string | null {
  if (typeof window === 'undefined') return 'Microphone is not available here.'
  if (!window.isSecureContext) {
    return (
      'Safari blocks the live mic on HTTP. Open this app on the Mac (localhost), or from the iPhone via Tailscale Serve HTTPS — see Settings. You can still attach a Voice Memo.'
    )
  }
  if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === 'undefined') {
    return 'This browser cannot record audio. Attach a Voice Memo instead.'
  }
  return null
}

export function pickRecorderMime(): string {
  if (typeof MediaRecorder === 'undefined') return ''
  const safari = /^((?!chrome|android).)*safari/i.test(navigator.userAgent)
  const types = safari
    ? ['audio/mp4', 'audio/aac', 'audio/webm']
    : ['audio/webm;codecs=opus', 'audio/webm', 'audio/mp4', 'audio/aac']
  return types.find((t) => MediaRecorder.isTypeSupported(t)) || ''
}

export function recorderExtension(mime: string): string {
  if (mime.includes('mp4') || mime.includes('aac')) return 'm4a'
  if (mime.includes('mpeg')) return 'mp3'
  return 'webm'
}

export async function transcribeBlob(blob: Blob, filename: string): Promise<string> {
  const file = new File([blob], filename, { type: blob.type || 'audio/webm' })
  const att = await uploadFile(file)
  return transcribeUpload(att.fileId)
}

function rmsFromTimeDomain(data: Uint8Array): number {
  let sum = 0
  for (const sample of data) {
    const n = (sample - 128) / 128
    sum += n * n
  }
  return Math.sqrt(sum / data.length)
}

export async function acquireMic(): Promise<MediaStream> {
  return navigator.mediaDevices.getUserMedia({
    audio: {
      echoCancellation: true,
      noiseSuppression: true,
      autoGainControl: true,
      channelCount: 1,
    },
  })
}

export function releaseMic(stream: MediaStream | null): void {
  stream?.getTracks().forEach((track) => track.stop())
}

export function setMicEnabled(stream: MediaStream | null, enabled: boolean): void {
  stream?.getAudioTracks().forEach((track) => {
    track.enabled = enabled
  })
}

interface ListenOnceOptions {
  onLevel?: (level: number) => void
  shouldStop: () => boolean
  maxMs?: number
  silenceMs?: number
  minSpeechMs?: number
  waitForSpeechMs?: number
  speechRms?: number
}

/**
 * Record one utterance from an already-open mic stream.
 * Safari often yields an empty blob unless we use a timeslice + requestData().
 */
export async function listenOnce(
  stream: MediaStream,
  options: ListenOnceOptions,
): Promise<Blob | null> {
  const {
    onLevel,
    shouldStop,
    maxMs = 25000,
    silenceMs = 1100,
    minSpeechMs = 450,
    waitForSpeechMs = 12000,
    speechRms = 0.035,
  } = options

  const mime = pickRecorderMime()
  const recorder = mime
    ? new MediaRecorder(stream, { mimeType: mime })
    : new MediaRecorder(stream)
  const chunks: Blob[] = []
  recorder.ondataavailable = (ev) => {
    if (ev.data.size > 0) chunks.push(ev.data)
  }

  const AudioCtx = window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext
  const audioCtx = new AudioCtx()
  const source = audioCtx.createMediaStreamSource(stream)
  const analyser = audioCtx.createAnalyser()
  analyser.fftSize = 2048
  source.connect(analyser)
  const samples = new Uint8Array(analyser.fftSize)
  const started = performance.now()
  let speechStartedAt: number | null = null
  let lastLoudAt: number | null = null

  try {
    recorder.start(200)
  } catch {
    recorder.start()
  }

  await new Promise<void>((resolve) => {
    const tick = () => {
      if (shouldStop()) {
        resolve()
        return
      }
      analyser.getByteTimeDomainData(samples as Uint8Array<ArrayBuffer>)
      const rms = rmsFromTimeDomain(samples)
      onLevel?.(Math.min(1, rms * 8))
      const now = performance.now()
      const elapsed = now - started
      if (rms >= speechRms) {
        if (speechStartedAt === null) speechStartedAt = now
        lastLoudAt = now
      }
      if (elapsed >= maxMs) {
        resolve()
        return
      }
      if (speechStartedAt === null && elapsed >= waitForSpeechMs) {
        resolve()
        return
      }
      if (
        speechStartedAt !== null &&
        lastLoudAt !== null &&
        now - speechStartedAt >= minSpeechMs &&
        now - lastLoudAt >= silenceMs
      ) {
        resolve()
        return
      }
      window.setTimeout(tick, 50)
    }
    tick()
  })

  const blob = await new Promise<Blob>((resolve) => {
    recorder.onstop = () => {
      const usedMime = recorder.mimeType || mime || 'audio/webm'
      resolve(new Blob(chunks, { type: usedMime }))
    }
    if (recorder.state === 'recording') {
      try {
        recorder.requestData()
      } catch {
        /* Safari may not implement requestData */
      }
      recorder.stop()
    } else {
      const usedMime = recorder.mimeType || mime || 'audio/webm'
      resolve(new Blob(chunks, { type: usedMime }))
    }
  })

  source.disconnect()
  await audioCtx.close().catch(() => {})

  if (shouldStop()) return null
  if (!speechStartedAt || blob.size < 800) return null
  return blob
}

export function blobFilename(blob: Blob): string {
  return `voice-turn.${recorderExtension(blob.type)}`
}
