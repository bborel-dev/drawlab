const ZOOM_LEVELS = [0.25, 0.5, 0.75, 1, 1.5, 2, 3, 4]
const FIT_ZOOM = 1

type ZoomControlProps = {
  zoom: number
  onChange: (zoom: number) => void
}

function ZoomControl({ zoom, onChange }: ZoomControlProps) {
  const zoomOut = ZOOM_LEVELS.findLast((level) => level < zoom)
  const zoomIn = ZOOM_LEVELS.find((level) => level > zoom)

  return (
    <div className="view-switch zoom-control" role="group" aria-label="Zoom">
      <button
        type="button"
        disabled={zoomOut === undefined}
        onClick={() => zoomOut && onChange(zoomOut)}
        aria-label="Zoom out"
      >
        −
      </button>
      <span className="zoom-value" aria-live="polite">
        {Math.round(zoom * 100)}%
      </span>
      <button
        type="button"
        disabled={zoomIn === undefined}
        onClick={() => zoomIn && onChange(zoomIn)}
        aria-label="Zoom in"
      >
        +
      </button>
      <button type="button" aria-pressed={zoom === FIT_ZOOM} onClick={() => onChange(FIT_ZOOM)}>
        Fit
      </button>
    </div>
  )
}

export default ZoomControl
