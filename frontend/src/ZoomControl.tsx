import { FIT_VIEW, ZOOM_LEVELS, type View } from './zoom'

type ZoomControlProps = {
  view: View
  onZoom: (zoom: number) => void
  onFit: () => void
}

function ZoomControl({ view, onZoom, onFit }: ZoomControlProps) {
  const { zoom } = view
  const zoomOut = ZOOM_LEVELS.findLast((level) => level < zoom)
  const zoomIn = ZOOM_LEVELS.find((level) => level > zoom)
  const fitted = zoom === FIT_VIEW.zoom && view.x === FIT_VIEW.x && view.y === FIT_VIEW.y

  return (
    <div className="view-switch zoom-control" role="group" aria-label="Zoom">
      <button
        type="button"
        disabled={zoomOut === undefined}
        onClick={() => zoomOut && onZoom(zoomOut)}
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
        onClick={() => zoomIn && onZoom(zoomIn)}
        aria-label="Zoom in"
      >
        +
      </button>
      <button type="button" aria-pressed={fitted} onClick={onFit}>
        Fit
      </button>
    </div>
  )
}

export default ZoomControl
