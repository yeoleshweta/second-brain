import { useEffect, useState, useRef } from 'react'
import { Document, Page, pdfjs } from 'react-pdf'
import { Loader2 } from 'lucide-react'
import { scrollToPercent, debounceByKey } from '@/lib/scrollProgress'
import 'react-pdf/dist/Page/AnnotationLayer.css'
import 'react-pdf/dist/Page/TextLayer.css'

pdfjs.GlobalWorkerOptions.workerSrc = new URL(
  'pdfjs-dist/build/pdf.worker.min.mjs',
  import.meta.url,
).toString()

interface Props {
  fileUrl: string
  title: string
  initialProgress?: number
  onScrollProgress?: (pct: number) => void
}

export function PdfScrollViewer({
  fileUrl,
  title,
  initialProgress = 0,
  onScrollProgress,
}: Props) {
  const [numPages, setNumPages] = useState(0)
  const [pageWidth, setPageWidth] = useState(640)
  const [loadError, setLoadError] = useState<string | null>(null)
  const scrollRef = useRef<HTMLDivElement>(null)
  const maxReported = useRef(0)
  const debounceTimers = useRef(new Map<string, ReturnType<typeof setTimeout>>())

  useEffect(() => {
    maxReported.current = initialProgress
  }, [fileUrl, initialProgress])

  useEffect(() => {
    const el = scrollRef.current
    if (!el || !onScrollProgress) return

    function handleScroll() {
      const pct = scrollToPercent(el!)
      if (pct <= maxReported.current) return
      maxReported.current = pct
      debounceByKey(debounceTimers.current, 'pdf', () => onScrollProgress!(pct), 600)
    }

    el.addEventListener('scroll', handleScroll, { passive: true })
    return () => {
      el.removeEventListener('scroll', handleScroll)
      const t = debounceTimers.current.get('pdf')
      if (t) clearTimeout(t)
    }
  }, [onScrollProgress, numPages])

  useEffect(() => {
    function updateWidth() {
      setPageWidth(Math.min(window.innerWidth - 32, 820))
    }
    updateWidth()
    window.addEventListener('resize', updateWidth)
    return () => window.removeEventListener('resize', updateWidth)
  }, [])

  return (
    <div ref={scrollRef} className="h-full overflow-y-auto bg-paper-200">
      <div className="max-w-3xl mx-auto px-4 py-4 pb-8 space-y-4">
        {numPages > 0 && (
          <p className="text-center text-[11px] text-paper-500 sticky top-0 z-10 py-1 bg-paper-200/90 backdrop-blur-sm">
            {title} · {numPages} {numPages === 1 ? 'page' : 'pages'} — scroll to read
          </p>
        )}

        <Document
          file={fileUrl}
          onLoadSuccess={({ numPages: pages }) => {
            setNumPages(pages)
            setLoadError(null)
          }}
          onLoadError={(err) => {
            setLoadError(err.message || 'Could not load PDF')
          }}
          loading={
            <div className="flex flex-col items-center justify-center py-20 text-paper-400 gap-2">
              <Loader2 size={28} className="animate-spin text-accent-400" />
              <p className="text-sm">Loading PDF…</p>
            </div>
          }
        >
          {Array.from({ length: numPages }, (_, index) => (
            <Page
              key={`page-${index + 1}`}
              pageNumber={index + 1}
              width={pageWidth}
              className="mx-auto shadow-card rounded-lg overflow-hidden bg-white"
              renderTextLayer
              renderAnnotationLayer
            />
          ))}
        </Document>

        {loadError && (
          <p className="text-center text-sm text-rust-500 py-8">{loadError}</p>
        )}
      </div>
    </div>
  )
}
