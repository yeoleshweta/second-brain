export type CaptureKind = 'log' | 'unsorted' | 'none' | 'queued'

export interface CaptureChip {
  kind: CaptureKind
  typeLabel: string
  phrase: string
  path?: string
  label: string
}

function phraseFor(kind: CaptureKind, typeLabel: string): string {
  if (kind === 'queued') return 'Static on the line.'
  if (kind === 'unsorted') return 'It slipped into the Upside Down.'
  if (kind === 'none') return 'Just between us.'
  if (typeLabel.toLowerCase() === 'food') return 'Fuel noted.'
  return "It's in the Void."
}

function chip(kind: CaptureKind, typeLabel: string, path?: string): CaptureChip {
  const label =
    kind === 'log'
      ? `Saved to Log as ${typeLabel}`
      : kind === 'unsorted'
        ? `Saved to Unsorted as ${typeLabel}`
        : kind === 'queued'
          ? 'Not saved yet, retrying'
          : 'Not saved'
  return { kind, typeLabel, phrase: phraseFor(kind, typeLabel), path, label }
}

export function splitCaptureStatus(content: string): { body: string; chip: CaptureChip } {
  let text = content
  let found: CaptureChip | null = null

  text = text.replace(/Saved under Log in `?([^\s`]+)`? as ([^.]+)\./g, (_m, path: string, type: string) => {
    found = chip('log', type.trim(), path)
    return ''
  })
  text = text.replace(/Saved under Unsorted in `?([^\s`]+)`?(?: \(([^)]+)\))?\.?/g, (_m, path: string, reason?: string) => {
    found = chip('unsorted', (reason || 'food or task?').trim(), path)
    return ''
  })
  text = text.replace(/Saved to `?([^\s`(]+)`? \(([^)]+)\)\./g, (_m, path: string, type: string) => {
    const kind: CaptureKind = /unsorted/i.test(type) ? 'unsorted' : 'log'
    found = chip(kind, type.trim(), path)
    return ''
  })
  text = text.replace(/Not saved yet\.[^\n]*/g, () => {
    if (!found) found = chip('queued', '')
    return ''
  })
  text = text.replace(/Not saved\.[^\n]*/g, () => '')

  return {
    body: text.replace(/\n{3,}/g, '\n\n').trim(),
    chip: found ?? chip('none', ''),
  }
}
