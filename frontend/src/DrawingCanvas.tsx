import { useEffect, useRef } from 'react'
import { animateDrawing } from './drawingAnimation'

type DrawingCanvasProps = {
  svg: string
}

function DrawingCanvas({ svg }: DrawingCanvasProps) {
  const containerRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const container = containerRef.current
    if (!container) return
    container.innerHTML = svg
    const svgElement = container.querySelector('svg')
    if (!svgElement) return
    const animations = animateDrawing(svgElement)
    return () => animations.forEach((animation) => animation.cancel())
  }, [svg])

  return <div className="drawing" ref={containerRef} />
}

export default DrawingCanvas
