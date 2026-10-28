import { useEffect, useLayoutEffect, useRef, useState, type KeyboardEvent, type PointerEvent, type RefObject } from 'react'
import type { Canvas } from './api'
import { layerTransform, type EditorLayer } from './editorLayers'
import { panBy, zoomAround, type View } from './zoom'

type ViewChange = (change: (view: View) => View) => void

type EditorCanvasProps = {
  canvas: Canvas
  layers: EditorLayer[]
  selectedId: string | null
  view: View
  onSelect: (id: string | null) => void
  onMove: (id: string, x: number, y: number) => void
  onViewChange: ViewChange
}

type Drag = {
  id: string
  pointerX: number
  pointerY: number
  x: number
  y: number
  unitsPerPixel: number
}

const NUDGE_STEP = 1
const LARGE_NUDGE_STEP = 10
const NUDGES: Record<string, [number, number]> = {
  ArrowLeft: [-1, 0],
  ArrowRight: [1, 0],
  ArrowUp: [0, -1],
  ArrowDown: [0, 1],
}
const WHEEL_ZOOM_SPEED = 0.01
const WHEEL_LINE_PIXELS = 16

function EditorCanvas({ canvas, layers, selectedId, view, onSelect, onMove, onViewChange }: EditorCanvasProps) {
  const stageRef = useRef<HTMLDivElement>(null)
  const svgRef = useRef<SVGSVGElement>(null)
  const dragRef = useRef<Drag | null>(null)
  const fitScale = useFitScale(stageRef, canvas)
  const selected = layers.find((layer) => layer.id === selectedId) ?? null
  const box = useLayerBox(svgRef, selected)
  const scale = fitScale * view.zoom
  useTrackpadView(stageRef, onViewChange)

  function startDrag(event: PointerEvent<SVGSVGElement>) {
    const layer = layers.find((candidate) => candidate.id === layerIdAt(event.target))
    onSelect(layer?.id ?? null)
    if (!layer) return
    event.currentTarget.setPointerCapture(event.pointerId)
    dragRef.current = {
      id: layer.id,
      pointerX: event.clientX,
      pointerY: event.clientY,
      x: layer.x,
      y: layer.y,
      unitsPerPixel: canvas.width / event.currentTarget.getBoundingClientRect().width,
    }
  }

  function drag(event: PointerEvent<SVGSVGElement>) {
    const current = dragRef.current
    if (!current) return
    const x = current.x + (event.clientX - current.pointerX) * current.unitsPerPixel
    const y = current.y + (event.clientY - current.pointerY) * current.unitsPerPixel
    onMove(current.id, Math.round(x), Math.round(y))
  }

  function nudge(event: KeyboardEvent<HTMLDivElement>) {
    if (event.key === 'Escape') onSelect(null)
    const direction = NUDGES[event.key]
    if (!selected || !direction) return
    event.preventDefault()
    const step = event.shiftKey ? LARGE_NUDGE_STEP : NUDGE_STEP
    onMove(selected.id, selected.x + direction[0] * step, selected.y + direction[1] * step)
  }

  return (
    <div
      ref={stageRef}
      className="editor-stage"
      tabIndex={0}
      aria-label="Canvas. Drag a layer to move it, use the arrow keys to nudge it, pinch to zoom, scroll to pan."
      onKeyDown={nudge}
      onPointerDown={(event) => event.target === event.currentTarget && onSelect(null)}
    >
      <svg
        ref={svgRef}
        className="editor-svg"
        xmlns="http://www.w3.org/2000/svg"
        width={canvas.width * scale}
        height={canvas.height * scale}
        style={{ transform: `translate(calc(-50% + ${view.x}px), calc(-50% + ${view.y}px))` }}
        viewBox={`0 0 ${canvas.width} ${canvas.height}`}
        onPointerDown={startDrag}
        onPointerMove={drag}
        onPointerUp={() => (dragRef.current = null)}
        onPointerCancel={() => (dragRef.current = null)}
      >
        {layers.map((layer) => (
          <g
            key={layer.id}
            data-layer={layer.id}
            transform={layerTransform(layer)}
            opacity={layer.opacity < 1 ? layer.opacity : undefined}
            display={layer.visible ? undefined : 'none'}
          >
            {layer.parts.map((part) => (
              <g
                key={part.id}
                display={part.visible ? undefined : 'none'}
                dangerouslySetInnerHTML={{ __html: part.markup }}
              />
            ))}
          </g>
        ))}
        {selected && box && (
          <rect
            className="selection-box"
            x={box.x + selected.x}
            y={box.y + selected.y}
            width={box.width}
            height={box.height}
            vectorEffect="non-scaling-stroke"
          />
        )}
      </svg>
    </div>
  )
}

function layerIdAt(target: EventTarget): string | null {
  if (!(target instanceof Element)) return null
  return target.closest('[data-layer]')?.getAttribute('data-layer') ?? null
}

function useFitScale(stageRef: RefObject<HTMLDivElement | null>, canvas: Canvas): number {
  const [fitScale, setFitScale] = useState(1)
  useLayoutEffect(() => {
    const stage = stageRef.current
    if (!stage) return
    const observer = new ResizeObserver(([entry]) => {
      const { width, height } = entry.contentRect
      if (width > 0 && height > 0) setFitScale(Math.min(width / canvas.width, height / canvas.height))
    })
    observer.observe(stage)
    return () => observer.disconnect()
  }, [stageRef, canvas])
  return fitScale
}


function useTrackpadView(stageRef: RefObject<HTMLDivElement | null>, onViewChange: ViewChange): void {
  useEffect(() => {
    const stage = stageRef.current
    if (!stage) return
    const onWheel = (event: WheelEvent) => {
      event.preventDefault()
      const unit = event.deltaMode === WheelEvent.DOM_DELTA_LINE ? WHEEL_LINE_PIXELS : 1
      if (!event.ctrlKey) {
        onViewChange((view) => panBy(view, { x: -event.deltaX * unit, y: -event.deltaY * unit }))
        return
      }
      const rect = stage.getBoundingClientRect()
      const point = { x: event.clientX - rect.left - rect.width / 2, y: event.clientY - rect.top - rect.height / 2 }
      const factor = Math.exp(-event.deltaY * unit * WHEEL_ZOOM_SPEED)
      onViewChange((view) => zoomAround(view, view.zoom * factor, point))
    }
    stage.addEventListener('wheel', onWheel, { passive: false })
    return () => stage.removeEventListener('wheel', onWheel)
  }, [stageRef, onViewChange])
}

function useLayerBox(svgRef: RefObject<SVGSVGElement | null>, layer: EditorLayer | null): DOMRect | null {
  const [box, setBox] = useState<DOMRect | null>(null)
  const layerId = layer?.visible ? layer.id : null
  const partsKey = layer?.parts.map((part) => part.visible).join() ?? ''
  useLayoutEffect(() => {
    const group = layerId ? svgRef.current?.querySelector<SVGGElement>(`[data-layer="${CSS.escape(layerId)}"]`) : null
    const measured = group?.getBBox() ?? null
    setBox(measured && measured.width + measured.height > 0 ? measured : null)
  }, [svgRef, layerId, partsKey])
  return box
}

export default EditorCanvas
