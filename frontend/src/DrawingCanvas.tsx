import { useEffect, useRef } from 'react'
import type { Canvas } from './api'
import { animateLayer, COLOR_DURATION_MS } from './drawingAnimation'
import { layerName } from './layers'

type DrawingCanvasProps = {
  canvas: Canvas
  layers: string[]
  onLayerStart: (name: string) => void
  onDrawingEndChange: (endsAt: number) => void
}

function DrawingCanvas({ canvas, layers, onLayerStart, onDrawingEndChange }: DrawingCanvasProps) {
  const svgRef = useRef<SVGSVGElement>(null)
  const drawnCountRef = useRef(0)
  const nextStartRef = useRef(0)
  const mountedRef = useRef(false)

  useEffect(() => {
    mountedRef.current = true
    return () => {
      mountedRef.current = false
    }
  }, [])

  useEffect(() => {
    const svg = svgRef.current
    if (!svg || drawnCountRef.current >= layers.length) return
    layers.slice(drawnCountRef.current).forEach((markup) => {
      const now = performance.now()
      const start = Math.max(now, nextStartRef.current)
      nextStartRef.current = start + animateLayer(appendLayer(svg, markup), canvas, start - now)
      const name = layerName(markup)
      window.setTimeout(() => mountedRef.current && onLayerStart(name), start - now)
    })
    drawnCountRef.current = layers.length
    onDrawingEndChange(nextStartRef.current + COLOR_DURATION_MS)
  }, [canvas, layers, onLayerStart, onDrawingEndChange])

  return (
    <svg
      ref={svgRef}
      className="drawing-svg"
      xmlns="http://www.w3.org/2000/svg"
      viewBox={`0 0 ${canvas.width} ${canvas.height}`}
      role="img"
      aria-label="Vector drawing"
    />
  )
}

function appendLayer(svg: SVGSVGElement, markup: string): Element {
  svg.insertAdjacentHTML('beforeend', markup)
  return svg.lastElementChild ?? svg
}

export default DrawingCanvas
