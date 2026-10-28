export const ZOOM_LEVELS = [0.25, 0.5, 0.75, 1, 1.5, 2, 3, 4, 6, 8]

const MIN_ZOOM = ZOOM_LEVELS[0]
const MAX_ZOOM = ZOOM_LEVELS[ZOOM_LEVELS.length - 1]

export type View = {
  zoom: number
  x: number
  y: number
}

export type Offset = {
  x: number
  y: number
}

export const FIT_VIEW: View = { zoom: 1, x: 0, y: 0 }

export function clampZoom(zoom: number): number {
  return Math.min(Math.max(zoom, MIN_ZOOM), MAX_ZOOM)
}

export function zoomAround(view: View, zoom: number, point: Offset = { x: 0, y: 0 }): View {
  const next = clampZoom(zoom)
  const ratio = next / view.zoom
  return { zoom: next, x: point.x - (point.x - view.x) * ratio, y: point.y - (point.y - view.y) * ratio }
}

export function panBy(view: View, offset: Offset): View {
  return { ...view, x: view.x + offset.x, y: view.y + offset.y }
}
