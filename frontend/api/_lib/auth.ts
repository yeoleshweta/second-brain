type HeaderBag = Record<string, string | string[] | undefined>

export function headerValue(headers: HeaderBag, name: string): string {
  const raw = headers[name] ?? headers[name.toLowerCase()]
  if (Array.isArray(raw)) return raw[0] ?? ''
  return raw ?? ''
}

export function expectedToken(): string {
  return (
    process.env.APP_API_TOKEN ||
    process.env.VITE_API_TOKEN ||
    'change-me-to-a-long-random-string'
  )
}

export function isAuthorized(headers: HeaderBag): boolean {
  const expected = expectedToken()
  const auth = headerValue(headers, 'authorization')
  const match = /^Bearer\s+(.+)$/i.exec(auth.trim())
  const got = match?.[1]?.trim() ?? ''
  return got.length > 0 && got === expected
}
