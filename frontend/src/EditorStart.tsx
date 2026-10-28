import { useEffect, useRef } from 'react'
import DropZone from './DropZone'
import { svgDocument, type Drawing } from './layers'
import type { RecentDrawing } from './recentDrawings'

type EditorStartProps = {
  recents: RecentDrawing[]
  error: string | null
  onOpenRecent: (id: string) => void
  onRemoveRecent: (id: string) => void
  onImport: (file: File) => void
  onConvert: () => void
}

const SVG_TYPES = 'image/svg+xml,.svg'
const RELATIVE_TIME = new Intl.RelativeTimeFormat('en', { numeric: 'auto' })
const TIME_UNITS: [Intl.RelativeTimeFormatUnit, number][] = [
  ['day', 86_400_000],
  ['hour', 3_600_000],
  ['minute', 60_000],
]

function EditorStart({ recents, error, onOpenRecent, onRemoveRecent, onImport, onConvert }: EditorStartProps) {
  return (
    <main className="editor-start glass">
      <div className="converter-row">
        <h1 className="start-title">Your drawings</h1>
        <button type="button" className="button button-secondary" onClick={onConvert}>
          Convert a new image
        </button>
      </div>
      {error && (
        <p className="error-banner" role="alert">
          {error}
        </p>
      )}
      {recents.length > 0 ? (
        <ul className="recent-grid">
          {recents.map((recent) => (
            <RecentCard
              key={recent.id}
              recent={recent}
              onOpen={() => onOpenRecent(recent.id)}
              onRemove={() => onRemoveRecent(recent.id)}
            />
          ))}
        </ul>
      ) : (
        <p className="panel-hint start-hint">
          Drawings you convert or open appear here. They stay in this browser only.
        </p>
      )}
      <DropZone
        onFile={onImport}
        title="Drop an SVG here"
        hint="Re-open an SVG exported from Drawlab"
        accept={SVG_TYPES}
        label="Open an SVG"
      />
    </main>
  )
}

type RecentCardProps = {
  recent: RecentDrawing
  onOpen: () => void
  onRemove: () => void
}

function RecentCard({ recent, onOpen, onRemove }: RecentCardProps) {
  const { drawing } = recent
  return (
    <li className="recent-card">
      <button type="button" className="recent-open" onClick={onOpen} aria-label={`Open ${drawing.sourceName}`}>
        <Thumbnail drawing={drawing} />
        <span className="recent-name">{drawing.sourceName}</span>
        <span className="recent-meta">
          {drawing.layers.length} layers · {timeAgo(recent.updatedAt)}
        </span>
      </button>
      <button
        type="button"
        className="recent-remove"
        onClick={onRemove}
        aria-label={`Remove ${drawing.sourceName} from recent drawings`}
        title="Remove"
      >
        ×
      </button>
    </li>
  )
}

function Thumbnail({ drawing }: { drawing: Drawing }) {
  const imageRef = useRef<HTMLImageElement>(null)
  useEffect(() => {
    const image = imageRef.current
    if (!image) return
    const blob = new Blob([svgDocument(drawing.canvas, drawing.layers)], { type: 'image/svg+xml' })
    const objectUrl = URL.createObjectURL(blob)
    image.src = objectUrl
    return () => URL.revokeObjectURL(objectUrl)
  }, [drawing])
  return (
    <span className="recent-thumb">
      <img ref={imageRef} alt="" />
    </span>
  )
}

function timeAgo(timestamp: number): string {
  const elapsed = timestamp - Date.now()
  const unit = TIME_UNITS.find(([, size]) => Math.abs(elapsed) >= size)
  return unit ? RELATIVE_TIME.format(Math.round(elapsed / unit[1]), unit[0]) : 'just now'
}

export default EditorStart
