import { useEffect, useRef } from 'react'
import type { Canvas } from './api'
import { animateLayer } from './drawingAnimation'

type DrawingCanvasProps = {
  canvas: Canvas
  layers: string[]
}

function DrawingCanvas({ canvas, layers }: DrawingCanvasProps) {
  const svgRef = useRef<SVGSVGElement>(null)
  const drawnCountRef = useRef(0)
  const nextStartRef = useRef(0)

  useEffect(() => {
    const svg = svgRef.current
    if (!svg) return
    layers.slice(drawnCountRef.current).forEach((markup) => {
      const now = performance.now()
      const start = Math.max(now, nextStartRef.current)
      nextStartRef.current = start + animateLayer(appendLayer(svg, markup), canvas, start - now)
    })
    drawnCountRef.current = layers.length
  }, [canvas, layers])

  return (
    <div className="drawing">
      <svg ref={svgRef} xmlns="http://www.w3.org/2000/svg" viewBox={`0 0 ${canvas.width} ${canvas.height}`} />
    </div>
  )
}

function appendLayer(svg: SVGSVGElement, markup: string): Element {
  svg.insertAdjacentHTML('beforeend', markup)
  return svg.lastElementChild ?? svg
}

export default DrawingCanvas
