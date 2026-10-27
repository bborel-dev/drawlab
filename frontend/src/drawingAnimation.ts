import type { Canvas } from './api'

const SVG_NS = 'http://www.w3.org/2000/svg'
const MIN_STROKE_MS = 250
const MAX_STROKE_MS = 1500
const DIAGONAL_STROKE_MS = 1500
const SKETCH_BUDGET_MS = 1200
const INK_BUDGET_MS = 2000
export const COLOR_DURATION_MS = 700
const MIN_STROKE_LENGTH_RATIO = 0.02
const INK_PASS_SELECTOR = '[data-pass="ink"]'
const SKETCH_COLOR = '#7a746d'
const SKETCH_OPACITY = 0.7
const SKETCH_WIDTH_RATIO = 1 / 1000
const INK_REVEAL_WIDTH_RATIO = 1 / 120

type Stroke = {
  path: SVGPathElement
  durationMs: number
}

let clipCount = 0

export function animateLayer(layer: Element, canvas: Canvas, startDelayMs: number): number {
  const paths = Array.from(layer.querySelectorAll('path'))
  paths.forEach(hidePath)
  const strokes = paths.map((path) => toStroke(path, canvas)).filter((stroke) => stroke !== null)
  const ink = strokes.filter((stroke) => isInk(stroke.path))
  const sketch = strokes.filter((stroke) => !isInk(stroke.path))
  const inkStart = drawSequence(sketch, startDelayMs, SKETCH_BUDGET_MS, (stroke, delay) =>
    drawSketchStroke(stroke, delay, canvas),
  )
  const colorStart = drawSequence(ink, inkStart, INK_BUDGET_MS, (stroke, delay) =>
    drawInkStroke(stroke, delay, canvas),
  )
  paths.forEach((path) => paintColor(path, colorStart))
  sketch.forEach(({ path }) => eraseSketch(path, colorStart))
  return colorStart - startDelayMs
}

function hidePath(path: SVGPathElement): void {
  path.style.fillOpacity = '0'
  path.style.strokeOpacity = '0'
}

function toStroke(path: SVGPathElement, canvas: Canvas): Stroke | null {
  const diagonal = Math.hypot(canvas.width, canvas.height)
  const length = path.getTotalLength()
  if (length < diagonal * MIN_STROKE_LENGTH_RATIO) return null
  const durationMs = Math.min(MAX_STROKE_MS, Math.max(MIN_STROKE_MS, (length / diagonal) * DIAGONAL_STROKE_MS))
  return { path, durationMs }
}

function isInk(path: SVGPathElement): boolean {
  return path.closest(INK_PASS_SELECTOR) !== null
}

function drawSequence(
  strokes: Stroke[],
  startMs: number,
  budgetMs: number,
  draw: (stroke: Stroke, delayMs: number) => void,
): number {
  const total = strokes.reduce((sum, stroke) => sum + stroke.durationMs, 0)
  const compression = Math.min(1, budgetMs / Math.max(total, 1))
  let cursor = startMs
  let end = startMs
  strokes.forEach((stroke) => {
    draw(stroke, cursor)
    end = Math.max(end, cursor + stroke.durationMs)
    cursor += stroke.durationMs * compression
  })
  return end
}

function drawSketchStroke({ path, durationMs }: Stroke, delayMs: number, canvas: Canvas): void {
  prepareStroke(path, SKETCH_COLOR, canvas.width * SKETCH_WIDTH_RATIO)
  path.style.strokeOpacity = String(SKETCH_OPACITY)
  revealStroke(path, delayMs, durationMs)
}

function drawInkStroke({ path, durationMs }: Stroke, delayMs: number, canvas: Canvas): void {
  prepareStroke(path, path.getAttribute('fill') ?? 'currentColor', canvas.width * INK_REVEAL_WIDTH_RATIO)
  path.style.strokeOpacity = '1'
  clipToItself(path)
  revealStroke(path, delayMs, durationMs)
}

function prepareStroke(path: SVGPathElement, color: string, width: number): void {
  path.setAttribute('pathLength', '1')
  path.style.stroke = color
  path.style.strokeWidth = String(width)
  path.style.strokeLinecap = 'round'
  path.style.strokeDasharray = '1'
  path.style.strokeDashoffset = '1'
}

function revealStroke(path: SVGPathElement, delayMs: number, durationMs: number): void {
  path.animate([{ strokeDashoffset: 1 }, { strokeDashoffset: 0 }], {
    duration: durationMs,
    delay: delayMs,
    easing: 'ease-in-out',
    fill: 'forwards',
  })
}

function clipToItself(path: SVGPathElement): void {
  const clip = document.createElementNS(SVG_NS, 'clipPath')
  clip.id = `ink-clip-${++clipCount}`
  const shape = document.createElementNS(SVG_NS, 'path')
  shape.setAttribute('d', path.getAttribute('d') ?? '')
  clip.append(shape)
  path.before(clip)
  path.setAttribute('clip-path', `url(#${clip.id})`)
}

function paintColor(path: SVGPathElement, delayMs: number): void {
  const paint = path.animate([{ fillOpacity: 0 }, { fillOpacity: 1 }], {
    duration: COLOR_DURATION_MS,
    delay: delayMs,
    easing: 'ease-out',
    fill: 'forwards',
  })
  paint.addEventListener('finish', () => restoreOriginal(path))
}

function restoreOriginal(path: SVGPathElement): void {
  path.getAnimations().forEach((animation) => animation.cancel())
  const clipId = path.getAttribute('clip-path')?.match(/#([^)]+)/)?.[1]
  if (clipId) document.getElementById(clipId)?.remove()
  path.removeAttribute('clip-path')
  path.removeAttribute('pathLength')
  path.removeAttribute('style')
}

function eraseSketch(path: SVGPathElement, delayMs: number): void {
  path.animate([{ strokeOpacity: SKETCH_OPACITY }, { strokeOpacity: 0 }], {
    duration: COLOR_DURATION_MS,
    delay: delayMs,
    easing: 'ease-out',
    fill: 'forwards',
  })
}
