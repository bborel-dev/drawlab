const STROKE_DURATION_MS = 700
const FILL_DURATION_MS = 500
const TARGET_TOTAL_MS = 15000
const MAX_STAGGER_MS = 60

export function animateDrawing(svg: SVGSVGElement): Animation[] {
  const paths = Array.from(svg.querySelectorAll('path'))
  const stagger = Math.min(MAX_STAGGER_MS, TARGET_TOTAL_MS / Math.max(paths.length, 1))
  const strokeWidth = svg.viewBox.baseVal.width / 600
  return paths.flatMap((path, index) => animatePath(path, index * stagger, strokeWidth))
}

function animatePath(path: SVGPathElement, delay: number, strokeWidth: number): Animation[] {
  preparePath(path, strokeWidth)
  const stroke = path.animate([{ strokeDashoffset: 1 }, { strokeDashoffset: 0 }], {
    duration: STROKE_DURATION_MS,
    delay,
    easing: 'ease-in-out',
    fill: 'forwards',
  })
  const paint = path.animate(
    [
      { fillOpacity: 0, strokeOpacity: 1 },
      { fillOpacity: 1, strokeOpacity: 0 },
    ],
    { duration: FILL_DURATION_MS, delay: delay + STROKE_DURATION_MS, easing: 'ease-out', fill: 'forwards' },
  )
  return [stroke, paint]
}

function preparePath(path: SVGPathElement, strokeWidth: number): void {
  path.setAttribute('pathLength', '1')
  path.style.stroke = path.getAttribute('fill') ?? 'currentColor'
  path.style.strokeWidth = String(strokeWidth)
  path.style.strokeDasharray = '1'
  path.style.strokeDashoffset = '1'
  path.style.fillOpacity = '0'
}
