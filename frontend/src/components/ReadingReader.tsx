import { useEffect, useState, useRef } from 'react'
import ReactMarkdown from 'react-markdown'
import { ArrowLeft, ExternalLink, FileText, Loader2 } from 'lucide-react'
import { PdfScrollViewer } from '@/components/PdfScrollViewer'
import { fetchReadingFile, getReadingContent } from '@/lib/api'
import { openExternalUrl } from '@/lib/openExternal'
import { scrollToPercent, debounceByKey } from '@/lib/scrollProgress'
import type { ReadingContent } from '@/lib/api'

interface ReadingReaderProps {
  itemId: number
  title: string
  url: string | null
  initialProgress?: number
  onProgress?: (pct: number) => void
  onClose: () => void
}

function looksLikePdfUrl(url: string | null | undefined): boolean {
  if (!url) return false
  const lower = url.toLowerCase()
  return lower.endsWith('.pdf') || lower.includes('arxiv.org/')
}

function isBrokenPdfScrape(body: string): boolean {
  const lower = body.toLowerCase()
  return (
    lower.includes('iframe that are currently hidden') ||
    lower.includes('consider enabling iframe processing')
  )
}

export function ReadingReader({
  itemId,
  title,
  url,
  initialProgress = 0,
  onProgress,
  onClose,
}: ReadingReaderProps) {
  const [content, setContent] = useState<ReadingContent | null>(null)
  const [pdfUrl, setPdfUrl] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const markdownScrollRef = useRef<HTMLDivElement>(null)
  const maxReported = useRef(0)
  const debounceTimers = useRef(new Map<string, ReturnType<typeof setTimeout>>())

  useEffect(() => {
    maxReported.current = initialProgress
  }, [itemId, initialProgress])

  useEffect(() => {
    const el = markdownScrollRef.current
    if (!el || !onProgress || content?.format === 'pdf') return

    function handleScroll() {
      const pct = scrollToPercent(el!)
      if (pct <= maxReported.current) return
      maxReported.current = pct
      debounceByKey(debounceTimers.current, 'md', () => onProgress!(pct), 600)
    }

    el.addEventListener('scroll', handleScroll, { passive: true })
    return () => {
      el.removeEventListener('scroll', handleScroll)
      const t = debounceTimers.current.get('md')
      if (t) clearTimeout(t)
    }
  }, [onProgress, content?.format, loading])

  const sourceUrl = content?.url || url

  useEffect(() => {
    let objectUrl: string | null = null
    let cancelled = false

    async function load() {
      setLoading(true)
      setError(null)
      setContent(null)
      setPdfUrl(null)

      try {
        const data = await getReadingContent(itemId)
        if (cancelled) return
        setContent(data)

        if (data.format === 'pdf') {
          const blob = await fetchReadingFile(itemId)
          if (cancelled) return
          objectUrl = URL.createObjectURL(blob)
          setPdfUrl(objectUrl)
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : 'Could not load content')
        }
      } finally {
        if (!cancelled) setLoading(false)
      }
    }

    load()

    return () => {
      cancelled = true
      if (objectUrl) URL.revokeObjectURL(objectUrl)
    }
  }, [itemId])

  const brokenPdfFallback =
    content?.format === 'markdown' &&
    (isBrokenPdfScrape(content.body || '') || looksLikePdfUrl(sourceUrl))

  return (
    <div className="fixed inset-0 z-50 flex flex-col bg-paper-100">
      <div
        className="shrink-0 bg-white border-b border-paper-200 px-4 py-3 flex items-center gap-3"
        style={{ paddingTop: 'max(env(safe-area-inset-top), 12px)' }}
      >
        <button
          onClick={onClose}
          className="w-9 h-9 flex items-center justify-center rounded-xl bg-paper-100 hover:bg-paper-200 text-paper-600 transition shrink-0"
          aria-label="Back to list"
        >
          <ArrowLeft size={18} />
        </button>
        <div className="flex-1 min-w-0">
          <h2 className="font-serif text-sm font-semibold text-paper-800 leading-snug line-clamp-2">
            {content?.title || title}
          </h2>
        </div>
        {sourceUrl && (
          <button
            type="button"
            onClick={() => openExternalUrl(sourceUrl)}
            className="w-9 h-9 flex items-center justify-center rounded-xl bg-paper-100 hover:bg-accent-50 text-paper-400 hover:text-accent-400 transition shrink-0"
            aria-label="Open in Safari"
          >
            <ExternalLink size={16} />
          </button>
        )}
      </div>

      <div className="flex-1 overflow-hidden">
        {loading ? (
          <div className="h-full flex flex-col items-center justify-center gap-3 text-paper-400">
            <Loader2 size={28} className="animate-spin text-accent-400" />
            <p className="text-sm">Loading article…</p>
          </div>
        ) : error ? (
          <div className="h-full flex flex-col items-center justify-center gap-3 px-6 text-center">
            <FileText size={32} className="text-paper-300" />
            <p className="text-sm text-rust-500">{error}</p>
            {sourceUrl && (
              <button
                type="button"
                onClick={() => openExternalUrl(sourceUrl)}
                className="text-sm font-semibold text-accent-500 hover:underline"
              >
                Open PDF in Safari
              </button>
            )}
          </div>
        ) : content?.format === 'pdf' && pdfUrl ? (
          <PdfScrollViewer
            fileUrl={pdfUrl}
            title={content.title}
            initialProgress={initialProgress}
            onScrollProgress={onProgress}
          />
        ) : brokenPdfFallback ? (
          <div className="h-full flex flex-col items-center justify-center gap-4 px-6 text-center">
            <FileText size={36} className="text-accent-300" />
            <div className="space-y-2 max-w-sm">
              <p className="text-sm font-semibold text-paper-800">PDF not cached yet</p>
              <p className="text-sm text-paper-500 leading-relaxed">
                Tap below to open the full paper in Safari. Re-open this item after a moment if
                you just saved it — Ross will retry the download.
              </p>
            </div>
            {sourceUrl && (
              <button
                type="button"
                onClick={() => openExternalUrl(sourceUrl)}
                className="inline-flex items-center gap-2 bg-accent-400 text-white text-sm font-semibold px-5 py-3 rounded-xl shadow-card active:scale-[0.99]"
              >
                <ExternalLink size={16} />
                Open PDF in Safari
              </button>
            )}
          </div>
        ) : (
          <div ref={markdownScrollRef} className="h-full overflow-y-auto px-4 py-6">
            <div className="max-w-2xl mx-auto bg-white rounded-2xl border border-paper-100 shadow-card px-5 py-6">
              <div className="prose-chat text-sm leading-relaxed break-words">
                <ReactMarkdown>{content?.body || ''}</ReactMarkdown>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
