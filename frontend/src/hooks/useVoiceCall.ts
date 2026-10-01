import { useCallback, useEffect, useRef, useState } from 'react'
import type { Attachment, Intent } from '@/types'
import {
  acquireMic,
  blobFilename,
  listenOnce,
  micBlockReason,
  micSupported,
  releaseMic,
  setMicEnabled,
  speakReply,
  stopSpeaking,
  transcribeBlob,
  unlockAudioPlayback,
  type VoicePhase,
} from '@/lib/voice'

export type ChatSendResult = {
  content: string
  intent?: Intent
  status?: 'complete' | 'error' | 'thinking'
}

type SendFn = (
  text: string,
  attachments: Attachment[],
) => Promise<ChatSendResult | void>

export function useVoiceCall(send: SendFn) {
  const [active, setActive] = useState(false)
  const [phase, setPhase] = useState<VoicePhase>('idle')
  const [level, setLevel] = useState(0)
  const [error, setError] = useState<string | null>(null)
  const generationRef = useRef(0)
  const streamRef = useRef<MediaStream | null>(null)
  const stopListenRef = useRef(false)
  const activeRef = useRef(false)

  const hangup = useCallback(() => {
    generationRef.current += 1
    activeRef.current = false
    stopListenRef.current = true
    stopSpeaking()
    releaseMic(streamRef.current)
    streamRef.current = null
    setActive(false)
    setPhase('idle')
    setLevel(0)
  }, [])

  const endUtterance = useCallback(() => {
    stopListenRef.current = true
    if (phase === 'speaking') stopSpeaking()
  }, [phase])

  const runLoop = useCallback(
    async (generation: number) => {
      while (generationRef.current === generation && activeRef.current) {
        const stream = streamRef.current
        if (!stream) break
        setMicEnabled(stream, true)
        stopListenRef.current = false
        setPhase('listening')
        setLevel(0)
        let blob: Blob | null = null
        try {
          blob = await listenOnce(stream, {
            onLevel: setLevel,
            shouldStop: () =>
              stopListenRef.current || generationRef.current !== generation,
          })
        } catch (err) {
          if (generationRef.current !== generation) return
          setError(err instanceof Error ? err.message : 'Mic recording failed.')
          continue
        }
        if (generationRef.current !== generation || !activeRef.current) return
        setLevel(0)
        if (!blob) continue

        setPhase('transcribing')
        setMicEnabled(stream, false)
        let spoken = ''
        try {
          spoken = (await transcribeBlob(blob, blobFilename(blob))).trim()
        } catch (err) {
          if (generationRef.current !== generation) return
          setError(
            err instanceof Error
              ? err.message
              : 'Could not transcribe. Check OPENAI_API_KEY.',
          )
          continue
        }
        if (generationRef.current !== generation || !activeRef.current) return
        if (!spoken || spoken.length < 2) continue
        setError(null)

        setPhase('waiting')
        const result = await send(spoken, [])
        if (generationRef.current !== generation || !activeRef.current) return
        const reply = (result?.content || '').trim()
        if (!reply) continue

        setPhase('speaking')
        try {
          await speakReply(reply, result?.intent)
        } catch (err) {
          if (generationRef.current !== generation) return
          setError(
            err instanceof Error
              ? err.message
              : 'Could not play the spoken reply.',
          )
        }
      }
    },
    [send],
  )

  const start = useCallback(async () => {
    setError(null)
    if (!micSupported()) {
      setPhase('blocked')
      setError(micBlockReason())
      setActive(true)
      return
    }
    const generation = generationRef.current + 1
    generationRef.current = generation
    activeRef.current = true
    setActive(true)
    setPhase('connecting')
    try {
      await unlockAudioPlayback()
      const stream = await acquireMic()
      if (generationRef.current !== generation) {
        releaseMic(stream)
        return
      }
      streamRef.current = stream
      await runLoop(generation)
    } catch {
      if (generationRef.current !== generation) return
      setPhase('blocked')
      setError('Microphone permission denied. You can still attach a Voice Memo.')
    }
  }, [runLoop])

  const toggle = useCallback(() => {
    if (activeRef.current) hangup()
    else void start()
  }, [hangup, start])

  useEffect(() => () => hangup(), [hangup])

  return {
    active,
    phase,
    level,
    error,
    micOk: micSupported(),
    blockReason: micBlockReason(),
    toggle,
    hangup,
    endUtterance,
  }
}
