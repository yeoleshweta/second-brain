import { list, put } from '@vercel/blob'

function token(): string {
  return process.env.BLOB_READ_WRITE_TOKEN || ''
}

export function blobConfigured(): boolean {
  return Boolean(token())
}

export async function readText(pathname: string): Promise<string | null> {
  const t = token()
  if (!t) return null
  const { blobs } = await list({ prefix: pathname, token: t, limit: 100 })
  const hit = blobs.find((b) => b.pathname === pathname)
  if (!hit) return null
  const url = hit.downloadUrl || hit.url
  const res = await fetch(url, { headers: { Authorization: `Bearer ${t}` } })
  if (res.status === 404) return null
  if (!res.ok) throw new Error(`blob read failed: ${res.status}`)
  return res.text()
}

export async function listPaths(prefix: string): Promise<string[]> {
  const t = token()
  if (!t) return []
  const { blobs } = await list({ prefix, token: t, limit: 500 })
  return blobs.map((b) => b.pathname)
}

export async function writeText(pathname: string, body: string, contentType: string): Promise<void> {
  const t = token()
  if (!t) throw new Error('BLOB_READ_WRITE_TOKEN is not set — enable Vercel Blob in this project.')
  await put(pathname, body, {
    access: 'private',
    addRandomSuffix: false,
    allowOverwrite: true,
    contentType,
    token: t,
  })
}
