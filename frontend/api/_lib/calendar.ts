const SCHEDULE_RE =
  /\b(schedule|book|set up|put (this |it |that )?(on|in)( my)? calendar|add (a |this |an? )?(meeting|event|call)|create( an?)? event|add (it |this |that )?to (my )?calendar)\b/i
const AGENDA_RE =
  /\b(what'?s? on (today|this week)|today'?s? agenda|agenda|what (do i have|am i doing) today|my schedule|what'?s? on my calendar)\b/i

export function classifyCalendarTurn(message: string): 'schedule' | 'agenda' | null {
  if (AGENDA_RE.test(message)) return 'agenda'
  if (SCHEDULE_RE.test(message)) return 'schedule'
  return null
}

export function skipsVault(message: string): boolean {
  return classifyCalendarTurn(message) !== null
}

export function calendarReply(message: string): string | null {
  const kind = classifyCalendarTurn(message)
  if (!kind) return null
  if (kind === 'agenda') {
    return (
      "I can list Google Calendar from the Mac app after you connect Google in Settings. " +
      "This phone deploy does not have that login, and I did not save this to the vault."
    )
  }
  return (
    "I can add that to Google Calendar after you confirm — from the Mac app with Google connected " +
    "(Settings → Connect Google). Say it there, then tap **Add to calendar**. " +
    "Nothing was written to the vault; only takeaways you approve in Review become notes."
  )
}
